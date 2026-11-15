# CodeTools

Many small tools, each a plugin with named actions. `schema` lists them all; `schema <id>` gives one plugin's actions and fields.

1. Find the plugin that does the job. If none does, say so rather than faking it.
2. Fill in its fields. Paths are paths on this computer.
3. Run it, read `lines`, `warnings` and `table`, look at `pictures`, and tell the user what came out and where the files are.

Plugins never delete. `tidy` moves files only by a plan the user has seen. An action marked `changes` touches the user's own files: do it only when they asked for exactly that.
