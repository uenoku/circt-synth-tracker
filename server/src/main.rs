//! Production-quality HTTP front end for `circt-synth-server`.
//!
//! * `POST /synthesize {mlir, top?, strategy?, ...}` — pooled backend
//!   workers (one `circt-synth-server --request-file` process each),
//!   bounded concurrency, per-request timeouts, SHA-256 fingerprint cache.
//! * `GET /health` — liveness + backend version probe.
//! * Optional `--db-dir`: persists every accepted result as a JSONL admit
//!   record plus content-addressed MLIR blob, compatible with the
//!   `circt_synth_tracker.db` schema (`db/meta.jsonl`, `db/blobs/`).

use axum::{
    Json, Router,
    extract::State,
    http::StatusCode,
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    path::PathBuf,
    sync::Arc,
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use tokio::{
    fs,
    process::Command,
    sync::{Mutex, Semaphore},
};

#[derive(Debug, Clone, Deserialize)]
struct SynthRequest {
    mlir: String,
    top: Option<String>,
    strategy: Option<String>,
    disable_datapath: Option<bool>,
    disable_timing_aware: Option<bool>,
    abc_commands: Option<Vec<String>>,
    abc_path: Option<String>,
    /// Seconds; falls back to server default.
    timeout_secs: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
struct SynthResponse {
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    mlir: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    cached: bool,
    version: String,
}

#[derive(Clone)]
struct AppConfig {
    backend: PathBuf,
    max_concurrent: usize,
    default_timeout: Duration,
    db_dir: Option<PathBuf>,
    version: String,
}

struct AppState {
    cfg: AppConfig,
    sem: Arc<Semaphore>,
    /// fingerprint -> response MLIR. Bounded by `CACHE_CAP` with crude
    /// oldest-eviction (insertion order tracked separately would be nicer;
    /// a HashMap + clear-on-full keeps v0 simple and correct).
    cache: Mutex<HashMap<String, String>>,
}

const CACHE_CAP: usize = 256;

fn fingerprint(req: &SynthRequest) -> String {
    // Canonical key: all fields that change the result, in fixed order.
    let canonical = serde_json::json!({
        "mlir": req.mlir,
        "top": req.top.as_deref().unwrap_or(""),
        "strategy": req.strategy.as_deref().unwrap_or("timing"),
        "disable_datapath": req.disable_datapath.unwrap_or(false),
        "disable_timing_aware": req.disable_timing_aware.unwrap_or(false),
        "abc_commands": req.abc_commands.clone().unwrap_or_default(),
        "abc_path": req.abc_path.as_deref().unwrap_or("abc"),
    });
    let bytes = serde_json::to_vec(&canonical).expect("serializable");
    format!("{:x}", Sha256::digest(bytes))
}

async fn run_backend(cfg: &AppConfig, req: &SynthRequest) -> SynthResponse {
    let dir = match tempfile_dir().await {
        Ok(d) => d,
        Err(e) => {
            return SynthResponse {
                ok: false,
                mlir: None,
                error: Some(format!("tempdir: {e}")),
                cached: false,
                version: cfg.version.clone(),
            }
        }
    };
    let req_path = dir.join("req.json");
    let resp_path = dir.join("resp.json");
    let body = serde_json::json!({
        "mlir": req.mlir,
        "top": req.top.as_deref().unwrap_or(""),
        "strategy": req.strategy.as_deref().unwrap_or("timing"),
        "disable_datapath": req.disable_datapath.unwrap_or(false),
        "disable_timing_aware": req.disable_timing_aware.unwrap_or(false),
        "abc_commands": req.abc_commands.clone().unwrap_or_default(),
        "abc_path": req.abc_path.as_deref().unwrap_or("abc"),
    });
    if let Err(e) = fs::write(&req_path, serde_json::to_vec(&body).unwrap()).await
    {
        return SynthResponse {
            ok: false,
            mlir: None,
            error: Some(format!("write request: {e}")),
            cached: false,
            version: cfg.version.clone(),
        };
    }
    let timeout = req.timeout_secs.map(Duration::from_secs).unwrap_or(cfg.default_timeout);
    let mut child = match Command::new(&cfg.backend)
        .arg("--request-file")
        .arg(&req_path)
        .arg("--response-file")
        .arg(&resp_path)
        .kill_on_drop(true)
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            return SynthResponse {
                ok: false,
                mlir: None,
                error: Some(format!("spawn backend: {e}")),
                cached: false,
                version: cfg.version.clone(),
            }
        }
    };
    match tokio::time::timeout(timeout, child.wait()).await {
        Ok(Ok(status)) if status.success() => {}
        Ok(Ok(status)) => {
            return SynthResponse {
                ok: false,
                mlir: None,
                error: Some(format!("backend exit: {status}")),
                cached: false,
                version: cfg.version.clone(),
            }
        }
        Ok(Err(e)) => {
            return SynthResponse {
                ok: false,
                mlir: None,
                error: Some(format!("wait backend: {e}")),
                cached: false,
                version: cfg.version.clone(),
            }
        }
        Err(_) => {
            return SynthResponse {
                ok: false,
                mlir: None,
                error: Some(format!("timeout after {}s", timeout.as_secs())),
                cached: false,
                version: cfg.version.clone(),
            }
        }
    }
    let data = match fs::read(&resp_path).await {
        Ok(d) => d,
        Err(e) => {
            return SynthResponse {
                ok: false,
                mlir: None,
                error: Some(format!("read response: {e}")),
                cached: false,
                version: cfg.version.clone(),
            }
        }
    };
    #[derive(Deserialize)]
    struct BackendResp {
        ok: bool,
        mlir: Option<String>,
        error: Option<String>,
    }
    let parsed: BackendResp = match serde_json::from_slice(&data) {
        Ok(p) => p,
        Err(e) => {
            return SynthResponse {
                ok: false,
                mlir: None,
                error: Some(format!("parse response: {e}")),
                cached: false,
                version: cfg.version.clone(),
            }
        }
    };
    SynthResponse {
        ok: parsed.ok,
        mlir: parsed.mlir,
        error: parsed.error,
        cached: false,
        version: cfg.version.clone(),
    }
}

async fn tempfile_dir() -> std::io::Result<PathBuf> {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let dir = std::env::temp_dir()
        .join(format!("synth-srv-{}-{}", std::process::id(), nanos));
    fs::create_dir_all(&dir).await?;
    Ok(dir)
}

fn blob_digest(data: &[u8]) -> String {
    format!("sha256:{:x}", Sha256::digest(data))
}

/// Append a JSONL admit record + blob compatible with `db/meta.jsonl`.
async fn admit_to_db(cfg: &AppConfig, fp: &str, out_mlir: &str) {
    let Some(root) = cfg.db_dir.clone() else { return };
    let blobs = root.join("blobs");
    let _ = fs::create_dir_all(&blobs).await;
    let digest = blob_digest(out_mlir.as_bytes());
    let blob_path = blobs.join(digest.replace(':', "_") + ".mlir");
    if fs::try_exists(&blob_path).await.unwrap_or(false) == false {
        let _ = fs::write(&blob_path, out_mlir.as_bytes()).await;
    }
    // Cost left for the judge pass; record key material + blob pointer.
    let record = serde_json::json!({
        "key": {"kind": "server-result", "fingerprint": fp},
        "kind": "server-result",
        "impl": {"blob": digest},
        "cost": {"gates": 0, "depth": 0},
        "proof": {"server": "circt-synth-server-rs"},
        "provenance": {"tool": "circt-synth-server-rs",
                       "version": cfg.version},
    });
    let meta = root.join("meta.jsonl");
    let mut line = serde_json::to_string(&record).unwrap_or_default();
    line.push('\n');
    // Best-effort append; a lost admit is just a cache miss later.
    if let Ok(mut f) = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&meta)
        .await
    {
        use tokio::io::AsyncWriteExt;
        let _ = f.write_all(line.as_bytes()).await;
    }
}

async fn synthesize(
    State(state): State<Arc<AppState>>,
    Json(req): Json<SynthRequest>,
) -> (StatusCode, Json<SynthResponse>) {
    if req.mlir.is_empty() {
        let r = SynthResponse {
            ok: false,
            mlir: None,
            error: Some("missing required field \"mlir\"".to_string()),
            cached: false,
            version: state.cfg.version.clone(),
        };
        return (StatusCode::BAD_REQUEST, Json(r));
    }
    if !matches!(req.strategy.as_deref().unwrap_or("timing"), "timing" | "area")
    {
        let r = SynthResponse {
            ok: false,
            mlir: None,
            error: Some("strategy must be \"area\" or \"timing\"".to_string()),
            cached: false,
            version: state.cfg.version.clone(),
        };
        return (StatusCode::BAD_REQUEST, Json(r));
    }
    let fp = fingerprint(&req);
    {
        let cache = state.cache.lock().await;
        if let Some(mlir) = cache.get(&fp) {
            let r = SynthResponse {
                ok: true,
                mlir: Some(mlir.clone()),
                error: None,
                cached: true,
                version: state.cfg.version.clone(),
            };
            return (StatusCode::OK, Json(r));
        }
    }
    // Bounded concurrency; queue beyond max_concurrent.
    let _permit = match state.sem.clone().acquire_owned().await {
        Ok(p) => p,
        Err(_) => {
            let r = SynthResponse {
                ok: false,
                mlir: None,
                error: Some("server shutting down".to_string()),
                cached: false,
                version: state.cfg.version.clone(),
            };
            return (StatusCode::SERVICE_UNAVAILABLE, Json(r));
        }
    };
    // Recheck after acquiring (thundering herd on same key).
    {
        let cache = state.cache.lock().await;
        if let Some(mlir) = cache.get(&fp) {
            let r = SynthResponse {
                ok: true,
                mlir: Some(mlir.clone()),
                error: None,
                cached: true,
                version: state.cfg.version.clone(),
            };
            return (StatusCode::OK, Json(r));
        }
    }
    let mut resp = run_backend(&state.cfg, &req).await;
    if resp.ok {
        if let Some(ref out) = resp.mlir.clone() {
            {
                let mut cache = state.cache.lock().await;
                if cache.len() >= CACHE_CAP {
                    cache.clear();
                }
                cache.insert(fp.clone(), out.clone());
            }
            admit_to_db(&state.cfg, &fp, &out).await;
        }
        (StatusCode::OK, Json(resp))
    } else {
        resp.cached = false;
        (StatusCode::INTERNAL_SERVER_ERROR, Json(resp))
    }
}

async fn health(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    // Probe the backend binary (cheap: --version) so health reflects reality.
    let backend_ok = Command::new(&state.cfg.backend)
        .arg("--version")
        .kill_on_drop(true)
        .output()
        .await
        .map(|o| o.status.success())
        .unwrap_or(false);
    Json(serde_json::json!({
        "status": if backend_ok { "ok" } else { "degraded" },
        "version": state.cfg.version,
        "backend_ok": backend_ok,
    }))
}

fn usage() -> ! {
    eprintln!(
        "usage: circt-synth-server-rs [--port N] [--bind ADDR] [--bin PATH]\n\
         \t[--jobs N] [--timeout SECS] [--db-dir DIR]"
    );
    std::process::exit(2);
}

#[tokio::main]
async fn main() {
    let mut port: u16 = 8932;
    let mut bind = "127.0.0.1".to_string();
    let mut backend = std::env::var("CIRCT_SYNTH_SERVER_BIN")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("circt-synth-server"));
    let mut jobs: usize = 4;
    let mut timeout = Duration::from_secs(600);
    let mut db_dir: Option<PathBuf> = None;
    let mut it = std::env::args().skip(1);
    while let Some(a) = it.next() {
        match a.as_str() {
            "--port" => port = it.next().unwrap_or_else(|| usage()).parse().unwrap_or_else(|_| usage()),
            "--bind" => bind = it.next().unwrap_or_else(|| usage()),
            "--bin" => backend = PathBuf::from(it.next().unwrap_or_else(|| usage())),
            "--jobs" => jobs = it.next().unwrap_or_else(|| usage()).parse().unwrap_or_else(|_| usage()),
            "--timeout" => timeout = Duration::from_secs(it.next().unwrap_or_else(|| usage()).parse().unwrap_or_else(|_| usage())),
            "--db-dir" => db_dir = Some(PathBuf::from(it.next().unwrap_or_else(|| usage()))),
            _ => usage(),
        }
    }
    let state = Arc::new(AppState {
        cfg: AppConfig {
            backend,
            max_concurrent: jobs,
            default_timeout: timeout,
            db_dir,
            version: env!("CARGO_PKG_VERSION").to_string(),
        },
        sem: Arc::new(Semaphore::new(jobs.max(1))),
        cache: Mutex::new(HashMap::new()),
    });
    // max_concurrent also sizes the semaphore; silence dead-field warning by use.
    let _ = state.cfg.max_concurrent;
    let app = Router::new()
        .route("/health", get(health))
        .route("/synthesize", post(synthesize))
        .with_state(state);
    let listener = tokio::net::TcpListener::bind((bind.as_str(), port))
        .await
        .expect("bind");
    eprintln!("circt-synth-server-rs on {bind}:{port}");
    axum::serve(listener, app).await.expect("serve");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn req(mlir: &str) -> SynthRequest {
        SynthRequest {
            mlir: mlir.to_string(),
            top: Some("add".to_string()),
            strategy: None,
            disable_datapath: None,
            disable_timing_aware: None,
            abc_commands: None,
            abc_path: None,
            timeout_secs: None,
        }
    }

    #[test]
    fn fingerprint_stable_and_option_sensitive() {
        let a = req("module {}");
        let b = req("module {}");
        assert_eq!(fingerprint(&a), fingerprint(&b));
        let mut c = req("module {}");
        c.strategy = Some("area".to_string());
        assert_ne!(fingerprint(&a), fingerprint(&c));
        let mut d = req("module  {}");
        assert_ne!(fingerprint(&a), fingerprint(&d));
    }

    #[test]
    fn blob_digest_format() {
        let d = blob_digest(b"abc");
        assert!(d.starts_with("sha256:"));
        assert_eq!(d.len(), 7 + 64);
    }

    #[tokio::test]
    async fn admit_writes_jsonl_and_blob() {
        let dir = std::env::temp_dir().join(format!(
            "srv-test-{}",
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ));
        let cfg = AppConfig {
            backend: PathBuf::from("nonexistent"),
            max_concurrent: 1,
            default_timeout: Duration::from_secs(1),
            db_dir: Some(dir.clone()),
            version: "test".to_string(),
        };
        admit_to_db(&cfg, "fp123", "module {}").await;
        let meta = fs::read_to_string(dir.join("meta.jsonl")).await.unwrap();
        let v: serde_json::Value = serde_json::from_str(meta.trim()).unwrap();
        assert_eq!(v["key"]["fingerprint"], "fp123");
        assert_eq!(v["kind"], "server-result");
        let blob = dir.join("blobs").read_dir().unwrap().count();
        assert_eq!(blob, 1);
    }

    // Integration (needs backend): run with
    // CIRCT_SYNTH_SERVER_BIN=.../circt-synth-server cargo test -- --ignored
    #[tokio::test]
    #[ignore]
    async fn roundtrip_through_backend() {
        let bin = std::env::var("CIRCT_SYNTH_SERVER_BIN")
            .expect("set CIRCT_SYNTH_SERVER_BIN");
        let cfg = AppConfig {
            backend: PathBuf::from(bin),
            max_concurrent: 1,
            default_timeout: Duration::from_secs(120),
            db_dir: None,
            version: "test".to_string(),
        };
        let mlir = "hw.module @add(in %a : i8, in %b : i8, out r : i8) {\n\
                    %0 = comb.add %a, %b : i8\n  hw.output %0 : i8\n}";
        // Note: bare hw.module needs an outer module wrapper for parsing.
        let wrapped = format!("module {{\n{mlir}\n}}\n");
        let r = SynthRequest {
            mlir: wrapped,
            top: Some("add".to_string()),
            strategy: None,
            disable_datapath: None,
            disable_timing_aware: None,
            abc_commands: None,
            abc_path: None,
            timeout_secs: None,
        };
        let resp = run_backend(&cfg, &r).await;
        assert!(resp.ok, "backend failed: {:?}", resp.error);
        let out = resp.mlir.unwrap();
        assert!(out.contains("synth.aig"), "not lowered:\n{out}");
        assert!(!out.contains("comb.add"), "comb.add survived:\n{out}");
    }
}
