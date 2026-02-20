import asyncio
import collections
import datetime
import itertools
import logging
import math
import random
import re
import statistics

from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import safe_builtins

logger = logging.getLogger(__name__)

def _get_safe_env():
    """
    Constructs a fresh safe environment for each execution.
    """
    env = safe_globals.copy()
    env['__builtins__'] = safe_builtins.copy()
    env.update({
        'math': math,
        'random': random,
        'datetime': datetime,
        're': re,
        'statistics': statistics,
        'itertools': itertools,
        'collections': collections,
    })
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
    try:
        byte_code = compile_restricted(code, '<inline>', 'exec')
    except Exception as e:
        return f"Syntax/Security Error: {e}", None
    env = _get_safe_env()
    import io
    output_buffer = io.StringIO()
    def _print(*args, **kwargs):
        print(*args, file=output_buffer, **kwargs)
    env['_print_'] = _print 
    env['print'] = _print
    try:
        exec(byte_code, env)
        output = output_buffer.getvalue()
        results = {}
        safe_keys = _get_safe_env().keys()
        for k, v in env.items():
            if k not in safe_keys and not k.startswith('_') and k != 'print':
                if not isinstance(v, (type(math), type(random))): 
                     results[k] = str(v)[:1000] # Truncate vars
                     
        return output, results
        
    except Exception as e:
        return output_buffer.getvalue(), f"Runtime Error: {e}"

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
        
        output, results_or_error = await loop.run_in_executor(
            None, 
            execute_restricted, 
            code
        )
        
        if output is None and results_or_error:
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
