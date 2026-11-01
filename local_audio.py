"""Control only the local PulseAudio sink; never send volume to AirPlay."""
import ctypes as C
import ctypes.util
import math,time

class Volume(C.Structure):
    _fields_=[('channels',C.c_uint8),('values',C.c_uint32*32)]

def set_output(percent):
    if not math.isfinite(percent) or not 0<=percent<=100:raise ValueError('Invalid output gain')
    lib=C.CDLL(ctypes.util.find_library('pulse') or 'libpulse.so.0')
    signatures={
      'pa_mainloop_new':(C.c_void_p,[]),'pa_mainloop_get_api':(C.c_void_p,[C.c_void_p]),
      'pa_mainloop_iterate':(C.c_int,[C.c_void_p,C.c_int,C.c_void_p]),'pa_mainloop_free':(None,[C.c_void_p]),
      'pa_context_new':(C.c_void_p,[C.c_void_p,C.c_char_p]),'pa_context_connect':(C.c_int,[C.c_void_p,C.c_char_p,C.c_int,C.c_void_p]),
      'pa_context_get_state':(C.c_int,[C.c_void_p]),'pa_context_disconnect':(None,[C.c_void_p]),'pa_context_unref':(None,[C.c_void_p]),
      'pa_context_set_sink_volume_by_name':(C.c_void_p,[C.c_void_p,C.c_char_p,C.POINTER(Volume),C.c_void_p,C.c_void_p]),
      'pa_operation_unref':(None,[C.c_void_p])}
    for name,(restype,args) in signatures.items():
        f=getattr(lib,name);f.restype=restype;f.argtypes=args
    loop=lib.pa_mainloop_new();ctx=None;operation=None
    if not loop:raise RuntimeError('PulseAudio mainloop unavailable')
    try:
        ctx=lib.pa_context_new(lib.pa_mainloop_get_api(loop),b'Echo local output policy')
        if not ctx or lib.pa_context_connect(ctx,b'unix:/run/echo-pulse/native',0,None)<0:raise RuntimeError('PulseAudio unavailable')
        deadline=time.monotonic()+2
        while lib.pa_context_get_state(ctx)!=4:
            if time.monotonic()>deadline or lib.pa_context_get_state(ctx) in (5,6):raise RuntimeError('PulseAudio unavailable')
            lib.pa_mainloop_iterate(loop,0,None);time.sleep(.005)
        volume=Volume();volume.channels=2
        volume.values[0]=volume.values[1]=round(percent/100*65536)
        completed=[]
        callback=C.CFUNCTYPE(None,C.c_void_p,C.c_int,C.c_void_p)(lambda context,success,userdata:completed.append(bool(success)))
        operation=lib.pa_context_set_sink_volume_by_name(ctx,b'AAudio_sink',C.byref(volume),callback,None)
        if not operation:raise RuntimeError('PulseAudio operation unavailable')
        while not completed:
            if time.monotonic()>deadline:raise RuntimeError('PulseAudio operation timed out')
            lib.pa_mainloop_iterate(loop,0,None);time.sleep(.005)
        if not completed[0]:raise RuntimeError('Output sink unavailable')
    finally:
        if operation:lib.pa_operation_unref(operation)
        if ctx:lib.pa_context_disconnect(ctx);lib.pa_context_unref(ctx)
        lib.pa_mainloop_free(loop)
