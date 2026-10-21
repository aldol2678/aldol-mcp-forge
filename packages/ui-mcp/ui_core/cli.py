"""Local artifact exporter: versioned UI JSON -> preview HTML or React TSX.

Never overwrites an existing file and never calls external services.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from . import core


def main() -> None:
    parser = argparse.ArgumentParser(description='ALDOL UI MCP Alpha 0.3.2 local generator')
    parser.add_argument('spec', type=Path, help='Versioned UI spec JSON')
    parser.add_argument('--target',choices=core.ALLOWED_TARGETS,default='web-html')
    parser.add_argument('--quality-mode',choices=['advisory','enforce'],default='advisory')
    parser.add_argument('--out',type=Path,required=True, help='New output directory (must not already exist)')
    args=parser.parse_args()
    # Validate before creating any output path; safety of output location belongs to operator.
    if args.out.exists(): parser.error('Output directory exists; refusing overwrite')
    result=core.render(args.spec.read_text(encoding='utf-8'),args.target,quality_mode=args.quality_mode)
    args.out.mkdir(parents=True)
    if args.target == 'react-tsx':
        (args.out/'AldolUI.generated.tsx').write_text(result['component_tsx'],encoding='utf-8')
    else:
        (args.out/'preview.html').write_text(result['preview_html'],encoding='utf-8')
        (args.out/'fragment.html').write_text(result['html'],encoding='utf-8')
        (args.out/'runtime.js').write_text(result['javascript'],encoding='utf-8')
    (args.out/'styles.css').write_text(result['css'],encoding='utf-8')
    print(f'Created {args.target} files in {args.out}')

if __name__ == '__main__': main()
