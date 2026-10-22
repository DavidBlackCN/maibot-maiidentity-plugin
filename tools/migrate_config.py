"""Offline migration CLI. Dry-run is mandatory before independent staging."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maiidentity.compatibility.migration import activate, apply, preview, public_report, rollback_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    action.add_argument("--activate", action="store_true")
    action.add_argument("--rollback-snapshot", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--namespace")
    parser.add_argument("--instance")
    parser.add_argument("--reviewed-source-sha256")
    parser.add_argument("--old-data-root", type=Path)
    parser.add_argument("--writer-lock", type=Path)
    parser.add_argument("--route-scope")
    parser.add_argument("--bootstrap-config", type=Path)
    parser.add_argument("--restore-to", type=Path)
    args = parser.parse_args()
    if not args.target.is_absolute():
        parser.error("target must be absolute")
    if args.activate:
        if not args.writer_lock or not args.route_scope:
            parser.error("--writer-lock and --route-scope required")
        result = activate(args.target, writer_lock=args.writer_lock, route_scope=args.route_scope, bootstrap_config=args.bootstrap_config)
    elif args.rollback_snapshot:
        if not args.restore_to:
            parser.error("--restore-to required")
        result = rollback_snapshot(args.target, args.restore_to)
    else:
        if not args.source or not args.source.is_absolute() or not args.namespace or not args.instance:
            parser.error("explicit absolute source, namespace and instance required")
        plan = preview(args.source, namespace=args.namespace, instance=args.instance)
        if args.apply:
            if args.reviewed_source_sha256 != plan["source_sha256"]:
                parser.error("dry-run first; pass --reviewed-source-sha256 from its report")
            result = apply(plan, args.target, old_data_root=args.old_data_root)
        else:
            result = public_report(plan, args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
