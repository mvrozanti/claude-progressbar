import ctypes
import struct


libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
libc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
libc.proc_pidinfo.restype = ctypes.c_int
libc.proc_pidfdinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
libc.proc_pidfdinfo.restype = ctypes.c_int
libc.proc_listpids.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int]
libc.proc_listpids.restype = ctypes.c_int
libc.sysctl.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
libc.sysctl.restype = ctypes.c_int


PROC_ALL_PIDS = 1
PROC_PPID_ONLY = 6
PROC_PIDTBSDINFO = 3
PROC_PIDFDVNODEPATHINFO = 2
BSDINFO_SIZE = 136
BSDINFO_PPID = 16
BSDINFO_COMM = slice(48, 64)
BSDINFO_START = 120
FDPATH_SIZE = 1200
MAXPATHLEN = 1024
CTL_KERN = 1
KERN_ARGMAX = 8
KERN_PROCARGS2 = 49
LISTING_SLOTS = 16384
ESRCH = 3


def failure():
    return OSError(ctypes.get_errno() or ESRCH, "process query failed")


def sysctl(names, size):
    mib = (ctypes.c_int * len(names))(*names)
    buf = ctypes.create_string_buffer(size)
    length = ctypes.c_size_t(size)
    if libc.sysctl(mib, len(names), buf, ctypes.byref(length), None, 0) != 0:
        raise failure()
    return buf.raw[:length.value]


_argmax = []


def argmax():
    if not _argmax:
        _argmax.append(struct.unpack("=i", sysctl([CTL_KERN, KERN_ARGMAX], 4))[0])
    return _argmax[0]


def info(pid):
    buf = ctypes.create_string_buffer(BSDINFO_SIZE)
    if libc.proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, buf, BSDINFO_SIZE) != BSDINFO_SIZE:
        raise failure()
    ppid = struct.unpack_from("=I", buf.raw, BSDINFO_PPID)[0]
    name = buf.raw[BSDINFO_COMM].split(b"\0")[0].decode("utf-8", "replace")
    sec, usec = struct.unpack_from("=QQ", buf.raw, BSDINFO_START)
    return name, ppid, sec + usec / 1e6


def argv(pid):
    data = sysctl([CTL_KERN, KERN_PROCARGS2, pid], argmax())
    argc = struct.unpack_from("=i", data)[0]
    rest = data[4:]
    i = rest.find(b"\0")
    while 0 <= i < len(rest) and rest[i] == 0:
        i += 1
    return [a.decode("utf-8", "replace") for a in rest[i:].split(b"\0")[:argc]]


def stdout(pid):
    buf = ctypes.create_string_buffer(FDPATH_SIZE)
    n = libc.proc_pidfdinfo(pid, 1, PROC_PIDFDVNODEPATHINFO, buf, FDPATH_SIZE)
    if n < MAXPATHLEN:
        raise failure()
    path = buf.raw[n - MAXPATHLEN:n].split(b"\0")[0]
    if not path:
        raise failure()
    return path.decode("utf-8", "replace")


def listing(kind, arg):
    buf = (ctypes.c_int * LISTING_SLOTS)()
    n = libc.proc_listpids(kind, arg, buf, ctypes.sizeof(buf))
    if n <= 0:
        return []
    return sorted({p for p in buf[:n // ctypes.sizeof(ctypes.c_int)] if p > 0})


def children(pid):
    return listing(PROC_PPID_ONLY, pid)


def everyone():
    return listing(PROC_ALL_PIDS, 0)
