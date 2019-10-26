import argparse
import datetime
from itertools import product
from os import makedirs

import numpy as np
import tensorflow as tf

from baseline_methods.pretraining import PretrainingBaseline
from datasets.synth_datasets import gen_sine_data, gen_tasks

# Parse arguments
argument_parser = argparse.ArgumentParser()
argument_parser.add_argument("--learning_rate", nargs="+", type=float, default=[3e-6],
                             help="Learning rate")
argument_parser.add_argument("--epochs", type=int, default=5000,
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
argument_parser.add_argument("--check_val_every", type=int, default=1,
                             help="Amount of epochs to pass before checking validation loss")

args = argument_parser.parse_args()

train_tasks = gen_tasks(args.n_functions)  # Generate tasks parameters
val_tasks = gen_tasks(10)

_, _, x_val, y_val = gen_sine_data(tasks=val_tasks, n_functions=args.n_functions,
                                   sample_length=args.sample_length,
                                   repetitions=args.repetitions)

# Numpy -> Tensorflow
x_val = tf.convert_to_tensor(x_val, dtype=tf.float32)
y_val = tf.convert_to_tensor(y_val, dtype=tf.float32)

# Main pre training loop
loss = float("inf")
# Create logs directories
current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
gen = product(list(range(1, 8)), list(range(1, 8)), args.learning_rate, [0.0000001, 0.0000003, 0.000001, 0.000003, 0.00001, 0.00003,
                                                                         0.0001, 0.0003, 0.001, 0.003])
p = PretrainingBaseline(tf.keras.losses.MeanSquaredError())
for tln_layers, rln_layers, lr, l2_lambda in gen:
    train_log_dir = f'logs/pt_isw_{lr}_rln{rln_layers}_tln{tln_layers}/' + current_time + '/pre_train'
    makedirs(train_log_dir, exist_ok=True)
    train_summary_writer = tf.summary.create_file_writer(train_log_dir)
    p.build_model(n_layers_rln=rln_layers, n_layers_tln=tln_layers)
    val_loss_counts = 0
    previous_val_loss = float("inf")
    val_loss = float("inf")
    for epoch in range(args.epochs):
        x_train, y_train, _, _ = gen_sine_data(tasks=train_tasks, n_functions=args.n_functions,
                                               sample_length=args.sample_length,
                                               repetitions=args.repetitions)

        # Reshape for inputting to training method
        x_train = np.vstack(x_train)
        y_train = np.vstack(y_train)

        # Numpy -> Tensorflow
        x_train = tf.convert_to_tensor(x_train, dtype=tf.float32)
        y_train = tf.convert_to_tensor(y_train, dtype=tf.float32)
        x_train = tf.reshape(x_train, (-1, args.n_functions + 1))
        y_train = tf.reshape(y_train, (-1,))

        training_loss = p.pre_train(x_train, y_train, learning_rate=lr, l2_lambda=l2_lambda)
        with train_summary_writer.as_default():
            tf.summary.scalar("Training Loss", training_loss, step=epoch)

        if epoch % args.check_val_every == 0:
            val_loss = p.compute_loss_no_training(x_val, y_val)
            with train_summary_writer.as_default():
                tf.summary.scalar("Validation Loss", val_loss, step=epoch)

            if previous_val_loss - val_loss < 1e-3:
                val_loss_counts += 1
                if val_loss_counts == 1:
                    p.save_model(f"final_lr{lr}_rln{rln_layers}_rln{tln_layers}_l2reg{l2_lambda}")
                elif val_loss_counts >= 50:
                    break
            else:
                previous_val_loss = val_loss
                val_loss_counts = 0

        # if epoch % args.save_models_every == 0:
        #     p.save_model(f"{epoch}_lr{lr}_rln{rln_layers}_tln{tln_layers}")
        #
