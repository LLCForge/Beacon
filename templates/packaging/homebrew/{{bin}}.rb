# Homebrew formula for {{name}}.
# Rendered by sync.py; @VERSION@ and the @SHA256_*@ values are filled in by the
# release workflow (job "publish", step "Render package-manager manifests") and
# shipped in {{bin}}-<version>-package-manifests.tar.gz. Copy the rendered file
# into the tap repository (LLCForge/homebrew-tap, Formula/{{bin}}.rb).
class {{formula_class}} < Formula
  desc "{{description}}"
  homepage "https://github.com/LLCForge/{{repo}}"
  version "@VERSION@"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/LLCForge/{{repo}}/releases/download/v@VERSION@/{{bin}}-@VERSION@-aarch64-apple-darwin.tar.gz"
      sha256 "@SHA256_AARCH64_APPLE_DARWIN@"
    end
    on_intel do
      url "https://github.com/LLCForge/{{repo}}/releases/download/v@VERSION@/{{bin}}-@VERSION@-x86_64-apple-darwin.tar.gz"
      sha256 "@SHA256_X86_64_APPLE_DARWIN@"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/LLCForge/{{repo}}/releases/download/v@VERSION@/{{bin}}-@VERSION@-aarch64-unknown-linux-musl.tar.gz"
      sha256 "@SHA256_AARCH64_LINUX_MUSL@"
    end
    on_intel do
      url "https://github.com/LLCForge/{{repo}}/releases/download/v@VERSION@/{{bin}}-@VERSION@-x86_64-unknown-linux-musl.tar.gz"
      sha256 "@SHA256_X86_64_LINUX_MUSL@"
    end
  end

  def install
    bin.install "{{bin}}"
    pkgetc.install "{{bin}}.example.toml" if File.exist?("{{bin}}.example.toml")
    doc.install Dir["README*.md"]
  end

  service do
    run [opt_bin/"{{bin}}", "run", "--config", etc/"{{bin}}/{{bin}}.toml"]
    environment_variables STATE_DIRECTORY: var/"lib/{{bin}}"
    keep_alive successful_exit: false
    log_path var/"log/{{bin}}.log"
    error_log_path var/"log/{{bin}}.log"
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/{{bin}} --version")
  end
end
