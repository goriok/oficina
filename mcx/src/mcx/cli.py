import typer

from mcx.commands import cluster, config, deploy, job, logs

app = typer.Typer(
    name="mcx",
    help="Cluster automation CLI for the oficina k3s cluster.",
    no_args_is_help=True,
)

app.add_typer(deploy.app, name="deploy")
app.add_typer(cluster.app, name="cluster")
app.add_typer(logs.app, name="logs")
app.add_typer(job.app, name="job")
app.add_typer(config.app, name="config")
