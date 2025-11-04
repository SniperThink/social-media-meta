import time
from typing import Callable, Any

def retry(func: Callable[..., Any], retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions=(Exception,), *f_args, **f_kwargs) -> Any:
    """Simple retry helper. Calls func and retries on exceptions.

    You can pass function args either positionally after the retry params or by named
    keyword `args` and `kwargs`, e.g. `retry(fn, retries=2, args=(x,), kwargs={'y':2})`.

    Returns func result or raises last exception.
    """
    # Support callers that pass func args as 'args' / 'kwargs' named parameters
    func_args = f_args
    func_kwargs = f_kwargs.copy()
    if 'args' in func_kwargs:
        # caller provided args as keyword
        func_args = tuple(func_kwargs.pop('args'))
    if 'kwargs' in func_kwargs:
        # caller provided kwargs as keyword
        provided_kw = func_kwargs.pop('kwargs')
        if isinstance(provided_kw, dict):
            func_kwargs.update(provided_kw)

    attempt = 0
    last_exc = None
    while attempt < retries:
        try:
            return func(*func_args, **func_kwargs)
        except exceptions as e:
            last_exc = e
            time.sleep(delay * (backoff ** attempt))
            attempt += 1
    raise last_exc
