import ctypes
import errno
from contextlib import contextmanager
from ctypes import wintypes


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
shell32 = ctypes.WinDLL("shell32", use_last_error=True)


TH32CS_SNAPPROCESS = 0x2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x10
PROCESS_DUP_HANDLE = 0x40
DUPLICATE_SAME_ACCESS = 0x2
FILE_TYPE_DISK = 0x1
PROCESS_BASIC_INFORMATION_CLASS = 0
PROCESS_COMMAND_LINE_CLASS = 60
EPOCH_AS_FILETIME = 116444736000000000
POINTER_SIZE = ctypes.sizeof(ctypes.c_void_p)
PARAMETERS_IN_PEB = 0x20 if POINTER_SIZE == 8 else 0x10
STDOUT_IN_PARAMETERS = 0x28 if POINTER_SIZE == 8 else 0x1C
INVALID_HANDLE = ctypes.c_void_p(-1).value
LONG_PATH = 32768


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ExitStatus", ctypes.c_long),
        ("PebBaseAddress", ctypes.c_void_p),
        ("AffinityMask", ctypes.c_size_t),
        ("BasePriority", ctypes.c_long),
        ("UniqueProcessId", ctypes.c_size_t),
        ("InheritedFromUniqueProcessId", ctypes.c_size_t),
    ]


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", ctypes.c_void_p)]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
kernel32.GetProcessTimes.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.DuplicateHandle.restype = wintypes.BOOL
kernel32.GetFileType.argtypes = [wintypes.HANDLE]
kernel32.GetFileType.restype = wintypes.DWORD
kernel32.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
kernel32.LocalFree.argtypes = [ctypes.c_void_p]
kernel32.LocalFree.restype = ctypes.c_void_p
ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
ntdll.NtQueryInformationProcess.restype = ctypes.c_long
shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)


def failure():
    code = ctypes.get_last_error()
    return ctypes.WinError(code) if code else OSError(errno.ESRCH, "process query failed")


_table = {}


def table():
    if not _table:
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snapshot or snapshot == INVALID_HANDLE:
            raise failure()
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while more:
                _table[entry.th32ProcessID] = (entry.szExeFile, entry.th32ParentProcessID)
                more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)
    return _table


@contextmanager
def process(pid, access):
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        raise failure()
    try:
        yield handle
    finally:
        kernel32.CloseHandle(handle)


def created(handle):
    times = [wintypes.FILETIME() for _ in range(4)]
    if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
        raise failure()
    ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    return (ticks - EPOCH_AS_FILETIME) / 1e7


def info(pid):
    entry = table().get(pid)
    if entry is None:
        raise OSError(errno.ESRCH, "no such process")
    with process(pid, PROCESS_QUERY_LIMITED_INFORMATION) as handle:
        return entry[0], entry[1], created(handle)


def command_line(handle):
    size = ctypes.c_ulong(0)
    ntdll.NtQueryInformationProcess(handle, PROCESS_COMMAND_LINE_CLASS, None, 0, ctypes.byref(size))
    if not size.value:
        raise failure()
    buf = ctypes.create_string_buffer(size.value)
    if ntdll.NtQueryInformationProcess(handle, PROCESS_COMMAND_LINE_CLASS, buf, size.value, ctypes.byref(size)) != 0:
        raise failure()
    text = UNICODE_STRING.from_buffer(buf)
    return ctypes.wstring_at(text.Buffer, text.Length // 2) if text.Buffer else ""


def split(line):
    if not line:
        return []
    count = ctypes.c_int(0)
    words = shell32.CommandLineToArgvW(line, ctypes.byref(count))
    if not words:
        raise failure()
    try:
        return [words[i] for i in range(count.value)]
    finally:
        kernel32.LocalFree(words)


def argv(pid):
    with process(pid, PROCESS_QUERY_LIMITED_INFORMATION) as handle:
        return split(command_line(handle))


def read_pointer(handle, address):
    value = ctypes.c_void_p()
    if not kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), ctypes.byref(value), POINTER_SIZE, None):
        raise failure()
    return value.value or 0


def remote_stdout(handle):
    basic = PROCESS_BASIC_INFORMATION()
    if ntdll.NtQueryInformationProcess(handle, PROCESS_BASIC_INFORMATION_CLASS, ctypes.byref(basic), ctypes.sizeof(basic), None) != 0:
        raise failure()
    if not basic.PebBaseAddress:
        raise failure()
    parameters = read_pointer(handle, basic.PebBaseAddress + PARAMETERS_IN_PEB)
    if not parameters:
        raise failure()
    return read_pointer(handle, parameters + STDOUT_IN_PARAMETERS)


def final_path(handle):
    if kernel32.GetFileType(handle) != FILE_TYPE_DISK:
        raise OSError(errno.ENOENT, "stdout is not a file")
    buf = ctypes.create_unicode_buffer(LONG_PATH)
    n = kernel32.GetFinalPathNameByHandleW(handle, buf, LONG_PATH, 0)
    if not n or n >= LONG_PATH:
        raise failure()
    path = buf.value
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    return path[4:] if path.startswith("\\\\?\\") else path


def stdout(pid):
    access = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ | PROCESS_DUP_HANDLE
    with process(pid, access) as handle:
        remote = remote_stdout(handle)
        if not remote:
            raise OSError(errno.ENOENT, "no stdout")
        local = wintypes.HANDLE()
        if not kernel32.DuplicateHandle(handle, remote, kernel32.GetCurrentProcess(), ctypes.byref(local), 0, False, DUPLICATE_SAME_ACCESS):
            raise failure()
    try:
        return final_path(local)
    finally:
        kernel32.CloseHandle(local)


def children(pid):
    return [child for child, (_, parent) in table().items() if parent == pid and child != pid]


def everyone():
    return list(table())
