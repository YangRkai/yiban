"""Configure the bundled offline engine without asking users for file paths."""
import json

def prepare_bundled_cpu(root):
    folder = root / 'engine-cpu'
    if not all((folder / name).is_file() for name in ('katago.exe', 'model.txt.gz', 'gtp.cfg')):
        return False
    target = root / 'board' / 'runtime.cpu.json'
    try:
        current = json.loads(target.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        current = {}
    if current and not current.get('bundled'):
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(executable=str(folder/'katago.exe'),
        model=str(folder/'model.txt.gz'), config=str(folder/'gtp.cfg'),
        dll_dirs=[str(folder)], label='KataGo · CPU', bundled=True), ensure_ascii=False), encoding='utf-8')
    return True
