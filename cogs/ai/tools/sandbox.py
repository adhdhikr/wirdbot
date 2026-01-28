import math
import random
import datetime
import re
import statistics
import itertools
import collections
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import safe_builtins

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---

# 1. Extend Safe Builtins
# We add generic utility types like 'list', 'dict', 'set' which are guarded by RestrictedPython
# Note: RestrictedPython safe_globals includes 'None', 'False', 'True', and guarded versions of basic types.

def _get_safe_env():
    """
    Constructs a fresh safe environment for each execution.
    """
    env = safe_globals.copy()
    env['__builtins__'] = safe_builtins.copy()
    
    # 2. Add Whitelisted Libraries
    env.update({
        'math': math,
        'random': random,
        'datetime': datetime,
        're': re,
        'statistics': statistics,
        'itertools': itertools,
        'collections': collections,
    })
    
    # 3. Add Safe Utilities
    # Allow simple printing (captured via wrapper in execution)
    # Allow range, len, etc (already in safe_builtins mostly)
    
    # Add 'sorted', 'reversed', 'enumerate', 'zip', 'map', 'filter' explicitly if safest versions aren't default
    env['__builtins__'].update({
        'sorted': sorted,
        'reversed': reversed,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'sum': sum,
        'min': min,
        'max': max,
        'abs': abs,
        'round': round
    })
    
    return env

def execute_restricted(code: str):
    """
    Compiles and runs code using RestrictedPython.
    """
    # 1. Compile (Checks for unsafe AST nodes like __subclasses__, dangerous names)
    try:
        byte_code = compile_restricted(code, '<inline>', 'exec')
    except Exception as e:
        return f"Syntax/Security Error: {e}", None

    # 2. Prepare Env
    env = _get_safe_env()
    
    # Custom Print Capture
    import io
    output_buffer = io.StringIO()
    def _print(*args, **kwargs):
        print(*args, file=output_buffer, **kwargs)
    
    # In RestrictedPython, 'print' function calls are often transformed to call '_print_'
    # We provide our capturer for both names to be safe.
    env['_print_'] = _print 
    env['print'] = _print
    
    # 3. Execute
    try:
        exec(byte_code, env)
        output = output_buffer.getvalue()
        
        # Extract likely result variables (non-underscore, non-library)
        results = {}
        safe_keys = _get_safe_env().keys()
        for k, v in env.items():
            if k not in safe_keys and not k.startswith('_') and k != 'print':
                # Don't return modules or callable functions we injected
                if not isinstance(v, (type(math), type(random))): 
                     results[k] = str(v)[:1000] # Truncate vars
                     
        return output, results
        
    except Exception as e:
        return output_buffer.getvalue(), f"Runtime Error: {e}"

# Remove the unused UnsafePrintStub class

async def run_python_script(code: str) -> str:
    """
    Executes a Python script in a RESTRICTED, SAFE sandbox (RestrictedPython).
    Use this for Math calculations, RNG, or Logic.
    
    Allowed: math, random, datetime, re, statistics, itertools, collections.
    Restricted: No imports, no IO, strict AST checking.
    
    Args:
        code: The python code to execute.
    """
    try:
        loop = asyncio.get_running_loop()
        
        # Run in thread with timeout logic?
        # RestrictedPython doesn't limit CPU time, just access.
        # We wrap in thread to avoid blocking main loop, but true infinite loop protection is hard without processes.
        # For now, simplistic execution.
        
        output, results_or_error = await loop.run_in_executor(
            None, 
            execute_restricted, 
            code
        )
        
        if output is None and results_or_error:
             # It was a compilation/runtime error
             return f"❌ {results_or_error}"
             
        response = ""
        if output:
            response += f"**Output:**\n```\n{output[:1000]}\n```\n"
            
        if isinstance(results_or_error, dict) and results_or_error:
             response += "**Result Variables:**\n```python\n"
             for k, v in results_or_error.items():
                 response += f"{k} = {v}\n"
             response += "```"

        if not response:
             return "✅ Script ran successfully (No output or variables)."
             
        return response

    except Exception as e:
        return f"❌ System Error: {e}"

SANDBOX_TOOLS = [
    run_python_script
]
