import subprocess, time, os, random, string

# Basit “stdin fuzz”: UCI akışına bozuk/garip komutlar atar
def random_garbage():
    letters = string.ascii_letters + string.digits + " :-_/\\\t"
    return "".join(random.choice(letters) for _ in range(random.randint(3, 40)))


def run(logger, report, path, seconds=10, instrumentation=None):
    report.add_test("uci_fuzz", seconds=seconds)
    try:
        p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except Exception as e:
        logger.log(f"[FUZZ] start fail: {e!r}")
        return
    t0 = time.time()
    # normal başlat
    try:
        p.stdin.write("uci\n"); p.stdin.flush()
    except Exception:
        pass

    if instrumentation:
        try:
            for name, value in instrumentation.uci_options.items():
                p.stdin.write(f"setoption name {name} value {value}\n")
            for cmd in getattr(instrumentation, "handshake_commands", []):
                p.stdin.write(cmd + "\n")
            p.stdin.flush()
        except Exception:
            pass

    while time.time() - t0 < seconds and p.poll() is None:
        payload = random.choice([
            "isready", "ucinewgame", "position startpos", "go movetime 1", random_garbage(), "go depth -5", "position fen X Y Z", "setoption name Threads value -3"
        ])
        try:
            p.stdin.write(payload + "\n"); p.stdin.flush()
        except Exception:
            break
        # stdout’u kısa okuyalım
        time.sleep(0.02)
        try:
            out = p.stdout.read(0)  # non-block
        except Exception:
            pass
    # sonlandır
    try:
        p.stdin.write("quit\n"); p.stdin.flush()
        time.sleep(0.1)
        p.kill()
    except Exception:
        pass
    code = p.poll()
    logger.log(f"[FUZZ] done, exit_code={code}")
