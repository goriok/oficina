import typer

from mcx.commands import cluster, companions, config, db, deploy, doctor, job, litellm, logs

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
app.add_typer(db.app, name="db")
app.add_typer(doctor.app, name="doctor")
app.add_typer(litellm.app, name="litellm")
app.add_typer(companions.app, name="companions")
