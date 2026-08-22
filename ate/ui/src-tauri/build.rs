# Minimal Tauri entry — build after: winget install Rustlang.Rustup
# Then: cd ate/ui && npm create tauri-app (or cargo tauri dev)

fn main() {
    println!("cargo:rerun-if-changed=tauri.conf.json");
}
