from os import makedirs
from os.path import isdir

import tensorflow as tf

from experiments.exp4_2.isw import mrcl_isw


class PretrainingBaseline:
    """
    Uses standard gradient descent to minimize prediction error of the pre-training set. We then fix the first few layers in online training. Rather than restricting to the same 6-2 architecture for the RLN and TLN, we pick the best split using a validation set.
    """
    def __init__(self, loss_function):
        self.model_rln = None
        self.model_tln = None
        self.loss_function = loss_function
        self.compute_loss_training = None
        self.compute_loss_no_training = None

    def build_model(self, n_layers_rln=6, n_layers_tln=2, hidden_units_per_layer=300, one_hot_depth=10):
        self.model_rln, self.model_tln = mrcl_isw(n_layers_rln, n_layers_tln, hidden_units_per_layer, one_hot_depth)
        self.compute_loss_training = tf.function(self._compute_loss)
        self.compute_loss_no_training = tf.function(self._compute_loss_no_regularization)

    def save_model(self, name):
        try:
            isdir("saved_models/")
        except NotADirectoryError:
            makedirs("saved_models/")
        self.model_rln.save(f"saved_models/{name}_rln.tf", save_format="tf")
        self.model_tln.save(f"saved_models/{name}_tln.tf", save_format="tf")

    def load_model(self, name):
        try:
            isdir("saved_models/")
        except NotADirectoryError:
            raise NotADirectoryError
        self.model_rln = tf.keras.models.load_model(f"saved_models/{name}_rln.tf")
        self.model_tln = tf.keras.models.load_model(f"saved_models/{name}_tln.tf")

    def _compute_loss(self, x, y, l2_lambda):
        w = self.model_tln.trainable_variables + self.model_rln.trainable_variables
        l2 = sum([tf.reduce_sum(v*v) for v in w])
        return self.loss_function(y, self.model_tln(self.model_rln(x))) + l2_lambda * l2

    def _compute_loss_no_regularization(self, x, y):
        return self.loss_function(y, self.model_tln(self.model_rln(x)))

    def pre_train(self, x_pre_train, y_pre_train, learning_rate, l2_lambda):
        with tf.GradientTape() as tape:
            loss = self.compute_loss_training(x_pre_train, y_pre_train, tf.constant(l2_lambda))
        params = self.model_rln.trainable_variables + self.model_tln.trainable_variables
        gradients = tape.gradient(loss, params)
        for p, g in zip(params, gradients):
            p.assign(p - g * learning_rate)
        return loss

    def evaluation(self, x_train, y_train, x_val, y_val):
        pass
