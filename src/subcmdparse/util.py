from typing import Tuple

import sh


def compile_shargs(*args, **kwargs) -> Tuple[list, dict]:
    shcmd = sh.Command('/bin/ls').bake(*args, **kwargs)
    return (
        [a.decode('utf-8') for a in shcmd._partial_baked_args],
        {'_' + k: i for k, i in shcmd._partial_call_args.items()}
    )