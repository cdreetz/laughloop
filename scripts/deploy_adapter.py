"""
LaughLoop Adapter Deployment — Deploy the latest trained adapter.

After an RL training run completes, this script:
1. Finds the latest adapter from the training run
2. Deploys it via the Prime API
3. Updates the backend's ADAPTER_ID env var / config

Usage:
  python scripts/deploy_adapter.py                     # auto-detect latest run
  python scripts/deploy_adapter.py --run-id <run_id>   # specific run
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add the project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from prime_cli.api.deployments import DeploymentsClient
    from prime_cli.api.rl import RLClient
    from prime_cli.core import APIClient, Config
except ImportError:
    print("Error: prime CLI not installed. Run: uv tool install prime")
    sys.exit(1)


def get_latest_run_id(rl_client: RLClient) -> str | None:
    """Find the most recent completed RL run."""
    runs = rl_client.list_runs()
    # Sort by created_at descending
    completed = [r for r in runs if r.status in ("COMPLETED", "STOPPED")]
    if not completed:
        return None
    completed.sort(key=lambda r: r.created_at, reverse=True)
    return completed[0].id


def get_latest_adapter(deployments_client: DeploymentsClient, run_id: str) -> dict | None:
    """Find the latest ready adapter for a training run."""
    adapters, total = deployments_client.list_adapters()
    # Filter by run ID and READY status
    matching = [
        a for a in adapters
        if a.rft_run_id == run_id and a.status == "READY"
    ]
    if not matching:
        return None
    # Sort by step (highest = latest)
    matching.sort(key=lambda a: a.step or 0, reverse=True)
    return matching[0]


def deploy_adapter(deployments_client: DeploymentsClient, adapter_id: str) -> bool:
    """Deploy an adapter and wait for it to be ready."""
    print(f"Deploying adapter {adapter_id}...")
    try:
        adapter = deployments_client.deploy_adapter(adapter_id)
        print(f"  Status: {adapter.deployment_status}")

        # Poll for deployment completion
        max_wait = 300  # 5 minutes
        start = time.time()
        while time.time() - start < max_wait:
            adapter = deployments_client.get_adapter(adapter_id)
            status = adapter.deployment_status
            print(f"  Deployment status: {status}")

            if status == "DEPLOYED":
                print(f"  Adapter deployed successfully!")
                return True
            elif status in ("DEPLOY_FAILED", "UNLOADING", "UNLOAD_FAILED"):
                print(f"  Deployment failed: {adapter.deployment_error}")
                return False

            time.sleep(10)

        print("  Timed out waiting for deployment")
        return False

    except Exception as e:
        print(f"  Error deploying adapter: {e}")
        return False


def update_backend_config(adapter_id: str):
    """Update the backend's adapter configuration."""
    # Write to a config file the backend can read
    config_path = Path(__file__).parent.parent / "app" / "backend" / ".adapter_config"
    config = {"adapter_id": adapter_id, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"Updated backend config: {config_path}")
    print(f"  Set LAUGHLOOP_ADAPTER_ID={adapter_id} and restart the backend to apply.")
    print(f"  Or run: LAUGHLOOP_ADAPTER_ID={adapter_id} python app/backend/server.py")


def main():
    parser = argparse.ArgumentParser(description="Deploy LaughLoop trained adapter")
    parser.add_argument("--run-id", help="Specific training run ID")
    parser.add_argument(
        "--skip-deploy", action="store_true",
        help="Skip API deployment (just update local config)"
    )
    args = parser.parse_args()

    api_client = APIClient()
    rl_client = RLClient(api_client)
    deployments_client = DeploymentsClient(api_client)

    # Find the run
    run_id = args.run_id
    if not run_id:
        print("Finding latest completed training run...")
        run_id = get_latest_run_id(rl_client)
        if not run_id:
            print("No completed training runs found.")
            return

    print(f"Using training run: {run_id}")

    # Find the adapter
    run = rl_client.get_run(run_id)
    print(f"  Model: {run.base_model}")
    print(f"  Status: {run.status}")
    print(f"  Steps: {run.max_steps}")

    adapter = get_latest_adapter(deployments_client, run_id)
    if not adapter:
        print("No ready adapters found for this run.")
        print("  Check: prime deployments list")
        return

    print(f"Found adapter: {adapter.id}")
    print(f"  Step: {adapter.step}")
    print(f"  Status: {adapter.status}")

    # Deploy
    if not args.skip_deploy:
        success = deploy_adapter(deployments_client, adapter.id)
        if not success:
            print("\nAdapter deployment failed. You can still use it locally.")
    else:
        print("Skipping API deployment (--skip-deploy)")

    # Update backend config
    update_backend_config(adapter.id)
    print("\n✅ Deployment complete! The model should now be funnier.")


if __name__ == "__main__":
    main()
