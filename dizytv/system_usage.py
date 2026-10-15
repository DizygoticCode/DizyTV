"""Lightweight, privacy-preserving desktop resource measurements.

Only Python's standard library is required. Sampling is opt-in while the
System usage window is open; no telemetry is uploaded or persisted.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import platform
import resource
import shutil
import sys
import time


def mib(byte_count):
    return round(byte_count / (1024 ** 2), 1)


def process_resident_bytes():
    """Return (RSS bytes, peak_only); current RSS wherever the OS supports it."""
    if sys.platform == 'win32':
        from ctypes import wintypes

        size_t = ctypes.c_size_t

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD),
                        ('PageFaultCount', wintypes.DWORD),
                        ('PeakWorkingSetSize', size_t),
                        ('WorkingSetSize', size_t),
                        ('QuotaPeakPagedPoolUsage', size_t),
                        ('QuotaPagedPoolUsage', size_t),
                        ('QuotaPeakNonPagedPoolUsage', size_t),
                        ('QuotaNonPagedPoolUsage', size_t),
                        ('PagefileUsage', size_t),
                        ('PeakPagefileUsage', size_t)]

        data = PROCESS_MEMORY_COUNTERS()
        data.cb = ctypes.sizeof(data)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(data), data.cb):
            return int(data.WorkingSetSize), False
        return None, False
    if sys.platform.startswith('linux'):
        try:
            for line in Path('/proc/self/status').read_text().splitlines():
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) * 1024, False
        except (OSError, ValueError, IndexError):
            pass
    # On macOS ru_maxrss is bytes; elsewhere the value is in KiB.
    try:
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak if sys.platform == 'darwin' else peak * 1024), True
    except (OSError, ValueError):
        return None, True


def physical_memory_bytes():
    """Return total and currently available physical RAM when supported."""
    if sys.platform == 'win32':
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [('dwLength', wintypes.DWORD),
                        ('dwMemoryLoad', wintypes.DWORD),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]

        data = MEMORYSTATUSEX()
        data.dwLength = ctypes.sizeof(data)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(data)):
            return int(data.ullTotalPhys), int(data.ullAvailPhys)
    elif sys.platform.startswith('linux'):
        try:
            rows = {}
            for line in Path('/proc/meminfo').read_text().splitlines():
                key, _, value = line.partition(':')
                if key in ('MemTotal', 'MemAvailable'):
                    rows[key] = int(value.split()[0]) * 1024
            if len(rows) == 2:
                return rows['MemTotal'], rows['MemAvailable']
        except (OSError, ValueError, IndexError):
            pass
    return None, None


class SystemSampler:
    """Nonblocking process CPU estimates and operating-system memory snapshots."""

    def __init__(self):
        self._last_time = None
        self._last_cpu = None

    def snapshot(self, data_directory=None):
        now = time.monotonic()
        times = os.times()
        consumed = times.user + times.system
        logical = max(1, os.cpu_count() or 1)
        process_cpu = None
        core_cpu = None
        if self._last_time is not None and now > self._last_time:
            interval = now - self._last_time
            core_cpu = round(max(0, consumed - self._last_cpu) / interval * 100, 1)
            process_cpu = round(core_cpu / logical, 1)
        self._last_time, self._last_cpu = now, consumed

        rss, peak_only = process_resident_bytes()
        total, available = physical_memory_bytes()
        disk_free = None
        if data_directory:
            try:
                disk_free = shutil.disk_usage(data_directory).free
            except OSError:
                pass
        return {
            'platform': platform.system(),
            'logical_cores': logical,
            'process_cpu_percent': process_cpu,
            'process_one_core_percent': core_cpu,
            'process_memory_mib': mib(rss) if rss is not None else None,
            'process_memory_peak_only': peak_only,
            'system_total_mib': mib(total) if total is not None else None,
            'system_used_mib': mib(total - available) if total is not None and available is not None else None,
            'system_used_percent': round(100 * (total-available) / total, 1) if total and available is not None else None,
            'recording_disk_free_gib': round(disk_free / (1024 ** 3), 1) if disk_free is not None else None,
        }
