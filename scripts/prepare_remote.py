"""One-time deployment administration; run as root, never callable by the organism."""
import ctypes
import os
from pathlib import Path
import pwd
import subprocess

ROOT = Path('/root/autodl-tmp/DigitalMonster')
if os.getuid() != 0:
    raise SystemExit('deployment preparation requires administrator privileges')
try:
    user = pwd.getpwnam('digitalmonster')
except KeyError:
    subprocess.run(['useradd', '--system', '--no-create-home', '--home-dir', str(ROOT/'data'),
                    '--shell', '/usr/sbin/nologin', 'digitalmonster'], check=True)
    user = pwd.getpwnam('digitalmonster')

# Allow this account to traverse /root to its designated data-volume directory.
# Preserve existing ACL entries and mask permissions; do not make /root listable.
lib = ctypes.CDLL('libacl.so.1', use_errno=True)
lib.acl_get_file.argtypes = [ctypes.c_char_p, ctypes.c_int]
lib.acl_get_file.restype = ctypes.c_void_p
lib.acl_to_text.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.acl_to_text.restype = ctypes.c_void_p
lib.acl_from_text.argtypes = [ctypes.c_char_p]
lib.acl_from_text.restype = ctypes.c_void_p
lib.acl_set_file.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
lib.acl_free.argtypes = [ctypes.c_void_p]
acl = lib.acl_get_file(b'/root', 0x8000)
if not acl:
    raise OSError(ctypes.get_errno(), 'read root ACL')
text_ptr = lib.acl_to_text(acl, None)
if not text_ptr:
    raise OSError(ctypes.get_errno(), 'render root ACL')
text = ctypes.string_at(text_ptr).decode()
lib.acl_free(text_ptr)
lib.acl_free(acl)
lines = [l for l in text.splitlines() if l and not l.startswith('user:digitalmonster:') and
         not l.startswith(f'user:{user.pw_uid}:')]
lines.append(f'user:{user.pw_uid}:--x')
mask = next((l.split(':')[2] for l in lines if l.startswith('mask::')), '---')
lines = [l for l in lines if not l.startswith('mask::')]
lines.append('mask::'+mask[:2]+'x')
new = lib.acl_from_text(('\n'.join(lines)+'\n').encode())
if not new or lib.acl_set_file(b'/root', 0x8000, new) != 0:
    raise OSError(ctypes.get_errno(), 'set service traversal ACL')
lib.acl_free(new)
for sub in ['data', 'data/research', 'data/experiments']:
    folder = ROOT/sub
    folder.mkdir(parents=True, exist_ok=True)
    os.chown(folder, user.pw_uid, user.pw_gid)
    folder.chmod(0o700)
print(f'service user uid={user.pw_uid}; writable data={ROOT / "data"}')

