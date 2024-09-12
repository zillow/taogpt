import pathlib as _pl
import sys as _sys
import math
import tiktoken as _tiktoken
import argparse


parser = argparse.ArgumentParser(
    prog='tc',
    description='LLM token count',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)

# hyperparameters
parser.add_argument('-l', '--llm', type=str, default='gpt-4', help='LLM model')
parser.add_argument('paths', type=str, nargs='+', default=None, help='One or more file or dir paths')


def main():
    args = parser.parse_args()
    try:
        enc = _tiktoken.encoding_for_model(args.llm)
    except KeyError:
        enc = _tiktoken.encoding_for_model('gpt-4')
    tokens: dict[_pl.Path, int] = dict()
    total_tokens = 0
    for p in args.paths:
        total_tokens += count_token(_pl.Path(p), enc, tokens)
    n_digits = int(math.ceil(math.log10(total_tokens)))
    fmt = f"{{0:>{n_digits}}} {{1}}"
    for p, n in tokens.items():
        print(fmt.format(n, p))
    print(fmt.format(total_tokens, f'TOTAL {args.llm} TOKENS'))


def count_token(file: _pl.Path, enc: _tiktoken.Encoding, tokens: dict[_pl.Path, int]) -> int:
    if file.is_dir():
        subtotal = 0
        for item in file.iterdir():
            subtotal += count_token(item, enc, tokens)
        return subtotal
    try:
        if file not in tokens:
            with open(file, 'r') as f:
                n_tokens = len(enc.encode(f.read()))
                tokens[file] = n_tokens
                return n_tokens
    except UnicodeDecodeError as e:
        print(f"WARNING: ignoring {file}. Not a tex file. {e}", file=_sys.stderr)
    except Exception as e:
        raise ValueError(f"[{file}] {e.__class__.__name__}: {e}")
    return 0


if __name__ == '__main__':
    main()
