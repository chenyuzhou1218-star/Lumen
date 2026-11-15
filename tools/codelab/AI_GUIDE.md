# Watching training with CodeLab

CodeLab reads training logs and reports, in numbers, what is happening. The user trains real models that take days. Be careful with them.

## Rules that are never broken

- Reading a log never touches the job writing it. That is all `watch`, `compare` and `picture` do.
- Never stop, restart or change a training job that CodeLab did not start, and never stop Python processes by name. `stop` refuses on its own.
- Starting a run needs the user's word: it takes the machine's memory and time, and may push out a job that is running.
- A file you were not asked to change stays as it is: scripts, checkpoints, data.

## The way of working

1. `watch <log>` and read it all: progress, the metrics, the warnings.
2. `picture <log>` and look at the curves.
3. Say what is going on in plain words: is it healthy, how long is left, is it worth going on? Give the numbers you read. If unsure, say so.
4. Suggestions are suggestions. The user decides.

## Commands

```
watch <log or name> [--name x]    what a log says. --name remembers it
list                              the runs CodeLab knows
compare <a> <b>                   the best values of several runs
picture <log> [-o file]           the curves
start <folder> --name x -- <cmd>  a new run in the background, with a log
stop <name>                       only a run CodeLab started
```

It reads any text log with lines like `loss: 0.31`, `epoch 3/10`, `step=100`, `{"loss": 0.31}`, tqdm bars, and CSV with named columns. If it finds no metrics, read part of the log yourself.

## Reading curves

- Falling fast, then slower, is healthy.
- Training loss down and validation loss up is overfitting. The best checkpoint is the one with the lowest validation loss, not the last.
- Flat from the start: the learning rate is too small, or the data is not reaching the model.
- Jumps and NaN: the learning rate is too big, or there is a bad sample.
