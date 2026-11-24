//! Spike (#1671): the desktop shell starts the local server from the bundled
//! Python runtime, waits until it is healthy, shows the UI it serves, and stops
//! it when the app quits. Timings go to spike-timings.log in the log folder.

use std::fs::{self, File, OpenOptions};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::webview::PageLoadEvent;
use tauri::{Manager, RunEvent, Url};

const PREFERRED_PORT: &str = "8765";
const HEALTH_PATH: &str = "/api/v1/admin/health";
const HEALTH_TIMEOUT: Duration = Duration::from_secs(120);
const STOP_GRACE: Duration = Duration::from_secs(10);

struct Backend(Mutex<Option<Child>>);

struct Timings {
    started: Instant,
    file: Mutex<File>,
}

impl Timings {
    fn record(&self, phase: &str) {
        let line = format!("{phase} {:.3}\n", self.started.elapsed().as_secs_f64());
        if let Ok(mut file) = self.file.lock() {
            let _ = file.write_all(line.as_bytes());
        }
    }
}

fn spawn_server(resources: &Path, data_dir: &Path, log_dir: &Path) -> std::io::Result<Child> {
    let payload = resources.join("payload");
    let stderr = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("server-stderr.log"))?;
    Command::new(payload.join("python/bin/python3"))
        .arg("-I")
        .arg("-B")
        .arg(payload.join("server/desktop_entry.py"))
        .arg("--data-dir")
        .arg(data_dir)
        .arg("--log-dir")
        .arg(log_dir)
        .arg("--ui-dir")
        .arg(payload.join("ui"))
        .arg("--hf-home")
        .arg(payload.join("hf"))
        .arg("--port")
        .arg(PREFERRED_PORT)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::from(stderr))
        .spawn()
}

/// True when GET path on the loopback port answers 200.
fn healthy(port: u16, path: &str) -> bool {
    let Ok(mut stream) = TcpStream::connect(("127.0.0.1", port)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let request = format!("GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    let _ = stream.read_to_string(&mut response);
    response.starts_with("HTTP/1.1 200")
}

fn show_error(app: &tauri::AppHandle, message: &str) {
    if let Some(window) = app.get_webview_window("main") {
        let text = serde_json::to_string(message).unwrap_or_default();
        let _ = window.eval(&format!(
            "document.getElementById('status').textContent = 'Context Studio could not start.';\
             const e = document.getElementById('error'); e.style.display = 'block'; e.textContent = {text};"
        ));
    }
}

/// Wait for the ready line and health, then show the UI; keep draining stdout after.
fn watch_server(app: tauri::AppHandle, stdout: impl Read + Send + 'static, log_dir: PathBuf) {
    thread::spawn(move || {
        let timings = app.state::<Timings>();
        let mut lines = BufReader::new(stdout).lines();
        let mut port: Option<u16> = None;
        for line in lines.by_ref().map_while(Result::ok) {
            if let Some(json) = line.strip_prefix("CS_READY ") {
                port = serde_json::from_str::<serde_json::Value>(json)
                    .ok()
                    .and_then(|v| v["port"].as_u64())
                    .and_then(|p| u16::try_from(p).ok());
                break;
            }
        }
        let Some(port) = port else {
            timings.record("server-exited-before-ready");
            show_error(&app, &format!("The server stopped while starting. See {}", log_dir.display()));
            return;
        };
        timings.record("ready-line");

        let deadline = Instant::now() + HEALTH_TIMEOUT;
        while !healthy(port, HEALTH_PATH) {
            if Instant::now() > deadline {
                timings.record("health-timeout");
                show_error(&app, &format!("The server did not become healthy. See {}", log_dir.display()));
                return;
            }
            thread::sleep(Duration::from_millis(100));
        }
        timings.record("healthy");

        if let (Some(window), Ok(url)) = (
            app.get_webview_window("main"),
            Url::parse(&format!("http://127.0.0.1:{port}/")),
        ) {
            let _ = window.navigate(url);
        }

        for _ in lines.map_while(Result::ok) {}
        timings.record("server-stdout-closed");
    });
}

/// Close the server's stdin so it shuts down cleanly; kill it after the grace period.
fn stop_server(app: &tauri::AppHandle) {
    let Some(mut child) = app.state::<Backend>().0.lock().ok().and_then(|mut c| c.take()) else {
        return;
    };
    drop(child.stdin.take());
    let deadline = Instant::now() + STOP_GRACE;
    while Instant::now() < deadline {
        if let Ok(Some(_)) = child.try_wait() {
            app.state::<Timings>().record("server-stopped");
            return;
        }
        thread::sleep(Duration::from_millis(100));
    }
    let _ = child.kill();
    let _ = child.wait();
    app.state::<Timings>().record("server-killed");
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let started = Instant::now();
    let app = tauri::Builder::default()
        .on_page_load(|webview, payload| {
            if payload.event() == PageLoadEvent::Finished {
                let phase = if payload.url().scheme() == "http" { "ui-loaded" } else { "splash-loaded" };
                webview.app_handle().state::<Timings>().record(phase);
            }
        })
        .setup(move |app| {
            let resources = app.path().resource_dir()?;
            let data_dir = app.path().app_data_dir()?;
            let log_dir = app.path().app_log_dir()?;
            fs::create_dir_all(&log_dir)?;
            let file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(log_dir.join("spike-timings.log"))?;
            app.manage(Timings { started, file: Mutex::new(file) });
            app.state::<Timings>().record("setup");

            let mut child = spawn_server(&resources, &data_dir, &log_dir)?;
            app.state::<Timings>().record("server-spawned");
            let stdout = child.stdout.take().expect("stdout is piped");
            app.manage(Backend(Mutex::new(Some(child))));
            watch_server(app.handle().clone(), stdout, log_dir);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            stop_server(app);
        }
    });
}
