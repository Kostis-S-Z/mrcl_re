import argparse
import datetime
from itertools import product
from os import makedirs

import numpy as np
import tensorflow as tf
import random
import tqdm

from baseline_methods.pretraining import PretrainingBaseline
from datasets.synth_datasets import gen_sine_data, gen_tasks

gpus = tf.config.experimental.list_physical_devices('GPU')
if len(gpus) > 0:
    tf.config.experimental.set_virtual_device_configuration(gpus[0], [
        tf.config.experimental.VirtualDeviceConfiguration(memory_limit=1024)])

# Parse arguments
argument_parser = argparse.ArgumentParser()
argument_parser.add_argument("--learning_rate", nargs="+", type=float, default=[3e-6],
                             help="Learning rate")
argument_parser.add_argument("--epochs", type=int, default=10000,
                             help="Number of epochs to pre train for")
argument_parser.add_argument("--n_tasks", type=int, default=400,
                             help="Number of tasks to pre train from")
argument_parser.add_argument("--n_functions", type=int, default=10,
                             help="Number of functions to sample per epoch")
argument_parser.add_argument("--sample_length", type=int, default=32,
                             help="Length of each sequence sampled")
argument_parser.add_argument("--repetitions", type=int, default=40,
                             help="Number of train repetitions for generating the data samples")
argument_parser.add_argument("--save_models_every", type=int, default=100,
                             help="Amount of epochs to pass before saving models")
argument_parser.add_argument("--check_val_every", type=int, default=100,
                             help="Amount of epochs to pass before checking validation loss")
argument_parser.add_argument("--layers_rln", type=int, nargs="+", default=6,
                             help="Amount of layers in the RLN and TLN")

args = argument_parser.parse_args()

train_tasks = gen_tasks(args.n_functions)  # Generate tasks parameters
val_tasks = gen_tasks(args.n_functions)

_, _, x_val, y_val = gen_sine_data(tasks=val_tasks, n_functions=args.n_functions,
                                   sample_length=args.sample_length,
                                   repetitions=args.repetitions, seed=0)

# Numpy -> Tensorflow
x_val = tf.convert_to_tensor(x_val, dtype=tf.float32)
y_val = tf.convert_to_tensor(y_val, dtype=tf.float32)

# Main pre training loop
loss = float("inf")
# Create logs directories
current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
layers_rln = args.layers_rln if type(args.layers_rln) is list else [args.layers_rln]
gen = product(layers_rln, args.learning_rate)
gen = list(gen)
random.shuffle(gen)
for layers_rln, lr in tqdm.tqdm(gen):
    layers_tln = 8 - layers_rln
    print(f"rln: {layers_rln}, tln: {layers_tln}, lr: {lr}")
    train_log_dir = f'logs/pt_isw_lr{lr}_rln{layers_rln}_tln{layers_tln}/' + current_time + '/pre_train'
    makedirs(train_log_dir, exist_ok=True)
    train_summary_writer = tf.summary.create_file_writer(train_log_dir)
    tf.keras.backend.clear_session()
    p = PretrainingBaseline(tf.keras.losses.MeanSquaredError())
    p.build_model(n_layers_rln=layers_rln, n_layers_tln=layers_tln, seed=0)
    val_loss_counts = 0
    previous_val_loss = p.compute_loss(x_val, y_val)
    with train_summary_writer.as_default():
        tf.summary.scalar("Validation Loss", previous_val_loss, step=0)
    val_loss = None
    for epoch in range(args.epochs):
        x_train, y_train, _, _ = gen_sine_data(tasks=train_tasks, n_functions=args.n_functions,
                                               sample_length=args.sample_length,
                                               repetitions=args.repetitions, seed=epoch)

        # Reshape for inputting to training method
        x_train = np.vstack(x_train)
        y_train = np.vstack(y_train)

        # According to figure 3, data comes IID
        indices = np.random.permutation(len(x_train))
        x_train = x_train[indices]
        y_train = y_train[indices]

        # Numpy -> Tensorflow
        x_train = tf.convert_to_tensor(x_train, dtype=tf.float32)
        y_train = tf.convert_to_tensor(y_train, dtype=tf.float32)
        x_train = tf.reshape(x_train, (-1, args.n_functions + 1))
        y_train = tf.reshape(y_train, (-1,))

        training_loss = float(p.pre_train(x_train, y_train, learning_rate=lr))

        if epoch % args.check_val_every == 0:
            with train_summary_writer.as_default():
                tf.summary.scalar("Training Loss", training_loss, step=epoch)
            val_loss = float(p.compute_loss(x_val, y_val))
            with train_summary_writer.as_default():
                tf.summary.scalar("Validation Loss", val_loss, step=epoch + 1)

            if previous_val_loss - val_loss < 1e-3:
                val_loss_counts += 1
                if val_loss_counts == 1:
                    p.save_model(f"pt_lr{lr}_rln{layers_rln}_tln{layers_tln}")
                elif val_loss_counts >= 6:
                    break
            else:
                previous_val_loss = float(val_loss)
                val_loss_counts = 0
