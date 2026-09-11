"""Create a portable source release without caches, packages or test artifacts."""
import gzip
import hashlib
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
  version = (ROOT / 'VERSION').read_text().strip()
  name = 'omarchy-parent-addons-' + version
  output = ROOT / 'dist' / (name + '.tar.gz')
  output.parent.mkdir(exist_ok=True)
  excluded = {'dist', 'pkg', 'src', '__pycache__', 'test-output', '.git'}
  with output.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
    with tarfile.open(fileobj=compressed, mode='w') as archive:
      for file in sorted(ROOT.rglob('*')):
        relative = file.relative_to(ROOT)
        if excluded.intersection(relative.parts) or file.name == '.DS_Store':
          continue
        if file.is_symlink():
          raise ValueError(f'Symlinks cannot be published: {relative}')
        if not file.is_file():
          continue
        info = archive.gettarinfo(str(file), arcname=name + '/' + str(relative))
        info.uid = info.gid = 0
        info.uname = info.gname = 'root'
        info.mtime = 0
        info.pax_headers = {}
        with file.open('rb') as source:
          archive.addfile(info, source)
  digest = hashlib.sha256(output.read_bytes()).hexdigest()
  output.with_name(output.name + '.sha256').write_text(digest + '  ' + output.name + '\n')
  print(output)
  print(f'{output.stat().st_size} bytes; SHA-256 {digest}')


if __name__ == '__main__':
  main()
