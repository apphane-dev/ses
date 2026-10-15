fn main() {
    // The Linux FFmpeg prebuilt in fframes 1.2 links x264 ABI 163. bootstrap.sh
    // downloads that genuine ABI on rolling distros without changing the system.
    let native =
        std::path::PathBuf::from(std::env::var_os("CARGO_MANIFEST_DIR").unwrap()).join(".native");
    println!("cargo:rerun-if-changed=.native");
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("linux")
        && native.join("libx264.so").exists()
    {
        println!("cargo:rustc-link-search=native={}", native.display());
        println!("cargo:rustc-link-arg=-Wl,-rpath,{}", native.display());
    }
}
