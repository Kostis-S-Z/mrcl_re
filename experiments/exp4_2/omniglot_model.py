from operator import itemgetter
import tensorflow_datasets as tfds
import tensorflow as tf
import numpy as np
from experiments.training import copy_parameters


def mrcl_omniglot_rln(inputs, n_layers, filters, strides=[2, 1, 2, 1, 2, 2]):
    h = inputs
    for i in range(n_layers):
        h = tf.keras.layers.Conv2D(filters, (3, 3), activation='relu', input_shape=(84, 84, 1), strides=strides[i])(h)
    h = tf.keras.layers.Flatten()(h)
    return h


def mrcl_omniglot_tln(inputs, n_layers, hidden_units_per_layer, output=964):
    y = inputs
    for i in range(n_layers - 1):
        y = tf.keras.layers.Dense(hidden_units_per_layer, activation='relu')(y)
    y = tf.keras.layers.Dense(output)(y)
    return y


def mrcl_omniglot(rln_layers=6, tln_layers=2, filters=256, hidden_units=300, classes=964):
    input_rln = tf.keras.Input(shape=(84, 84, 1))
    input_tln = tf.keras.Input(shape=3 * 3 * 256)
    h = mrcl_omniglot_rln(input_rln, rln_layers, filters)
    rln = tf.keras.Model(inputs=input_rln, outputs=h)
    y = mrcl_omniglot_tln(input_tln, tln_layers, hidden_units, output=classes)
    tln = tf.keras.Model(inputs=input_tln, outputs=y)
    return rln, tln


def get_background_data_by_classes(background_data, sort=True):
    if sort:
        background_data = np.array(sorted(list(tfds.as_numpy(background_data)), key=itemgetter('label')))
    else:
        background_data = np.array(list(tfds.as_numpy(background_data)))
        np.random.shuffle(background_data)

    background_training_data = []
    background_training_data_15 = []
    background_training_data_5 = []
    background_number_of_classes = int(background_data.shape[0] / 20)

    for i in range(background_number_of_classes):
        background_training_data.append(background_data[i * 20:(i + 1) * 20])
        background_training_data_15.append(background_data[i * 20:i * 20 + 15])
        background_training_data_5.append(background_data[i * 20 + 15:(i + 1) * 20])

    return background_training_data, background_training_data_15, background_training_data_5


def get_eval_data_by_classes(evaluation_data):
    evaluation_data = np.array(sorted(list(tfds.as_numpy(evaluation_data)), key=itemgetter('label')))
   
    evaluation_training_data = []
    evaluation_test_data = []
    evaluation_number_of_classes = int(evaluation_data.shape[0] / 20)
    for i in range(evaluation_number_of_classes):
        evaluation_training_data.append(evaluation_data[i * 20:i * 20 + 15])
        evaluation_test_data.append(evaluation_data[i * 20 + 15:(i + 1) * 20])

    return evaluation_training_data, evaluation_test_data


def partition_into_disjoint(data):
    number_of_classes = len(data)
    s_learn = list(range(0, int(number_of_classes / 2)))
    s_remember = list(range(int(number_of_classes / 2), number_of_classes))
    return s_learn, s_remember


def sample_trajectory(s_learn, data):
    random_class = np.random.choice(s_learn)
    x_traj = []
    y_traj = []
    for item in data[random_class]:
        x_traj.append(item['image'])
        y_traj.append(item['label'])
    return tf.convert_to_tensor(x_traj), tf.convert_to_tensor(y_traj)


def sample_random(s_remember, data):
    random_class = np.random.choice(s_remember)
    x_rand = []
    y_rand = []
    for item in data[random_class]:
        x_rand.append(item['image'])
        y_rand.append(item['label'])
    return tf.convert_to_tensor(x_rand), tf.convert_to_tensor(y_rand)

def sample_random_10_classes(s_remember, data):
    random_classes = np.random.choice(s_remember, 10)
    x_rand = []
    y_rand = []
    for random_class in random_classes:
        random_index = np.random.choice(list(range(20)))
        x_rand.append(data[random_class][random_index]['image'])
        y_rand.append(data[random_class][random_index]['label'])
    return tf.convert_to_tensor(x_rand), tf.convert_to_tensor(y_rand)


def pretrain_classification_mrcl(x_traj, y_traj, x_rand, y_rand, rln, tln, tln_initial, classification_parameters):
    # Random reinitialization of last layer
    w = tln.layers[-1].weights[0]
    new_w = tln.layers[-1].kernel_initializer(shape=w.shape)
    tln.layers[-1].weights[0].assign(new_w)

    # Clone tln to preserve initial weights
    copy_parameters(tln, tln_initial)

    x_meta = tf.concat([x_rand, x_traj], axis=0)
    y_meta = tf.concat([y_rand, y_traj], axis=0)

    for x, y in zip(x_traj, y_traj):
        inner_update(x, y, rln, tln, classification_parameters)

    with tf.GradientTape(persistent=True) as theta_tape:
        outer_loss, _ = compute_loss(x_meta, y_meta, rln, tln, classification_parameters)

    tln_gradients = theta_tape.gradient(outer_loss, tln.trainable_variables)
    rln_gradients = theta_tape.gradient(outer_loss, rln.trainable_variables)
    del theta_tape

    classification_parameters["meta_optimizer"](
        learning_rate=classification_parameters["meta_learning_rate"]).apply_gradients(
        zip(tln_gradients + rln_gradients, tln_initial.trainable_variables + rln.trainable_variables))

    copy_parameters(tln_initial, tln)
    return outer_loss


#@tf.function
def inner_update(x, y, rln, tln, classification_parameters):
    with tf.GradientTape(watch_accessed_variables=False) as Wj_Tape:
        Wj_Tape.watch(tln.trainable_variables)
        inner_loss, _ = compute_loss(x, y, rln, tln, classification_parameters)
    gradients = Wj_Tape.gradient(inner_loss, tln.trainable_variables)
    for g, v in zip(gradients, tln.trainable_variables):
        v.assign(v - classification_parameters["inner_learning_rate"] * g)


#@tf.function
def compute_loss(x, y, rln, tln, classification_parameters):
    if x.shape.ndims == 3:
        output = tln(rln(tf.expand_dims(x, axis=0)))
    else:
        output = tln(rln(x))
    loss = classification_parameters["loss_function"](y, output)
    return loss, output


def evaluate_classification_mrcl(training_data, testing_data, rln, tln, number_of_classes, classification_parameters):
    all_classes = list(range(len(training_data)))
    classes_to_use = np.random.choice(all_classes, number_of_classes)

    x_training = []
    y_training = []
    x_testing = []
    y_testing = []
    temp_class_id = 0
    for class_id in classes_to_use:
        for training_item in training_data[class_id]:
            x_training.append(training_item['image'])
            y_training.append(temp_class_id)
        for testing_item in testing_data[class_id]:
            x_testing.append(testing_item['image'])
            y_testing.append(temp_class_id)
        temp_class_id = temp_class_id + 1

    x_training = tf.convert_to_tensor(x_training)
    y_training = tf.convert_to_tensor(y_training)
    x_testing = tf.convert_to_tensor(x_testing)
    y_testing = tf.convert_to_tensor(y_testing)
    for m in range(x_training.shape[0]):
        with tf.GradientTape() as tape:
            loss, _ = compute_loss(x_training[m], y_training[m], rln, tln, classification_parameters)
        gradient_tln = tape.gradient(loss, tln.trainable_variables)
        classification_parameters['online_optimizer'](
            learning_rate=classification_parameters['online_learning_rate']).apply_gradients(
            zip(gradient_tln, tln.trainable_variables))

    data = tf.data.Dataset.from_tensor_slices((x_training, y_training)).batch(256)
    total_correct = 0
    for x, y in data:
        loss, output = compute_loss(x, y, rln, tln, classification_parameters)
        after_softmax = tf.nn.softmax(output, axis=1)
        correct_prediction = tf.equal(tf.cast(tf.argmax(after_softmax, axis=1), tf.int32), y)
        total_correct = total_correct + tf.reduce_sum(tf.cast(correct_prediction, tf.float32))
    train_accuracy = total_correct/x_training.shape[0]

    data = tf.data.Dataset.from_tensor_slices((x_testing, y_testing)).batch(256)
    total_correct = 0
    for x, y in data:
        loss, output = compute_loss(x, y, rln, tln, classification_parameters)
        after_softmax = tf.nn.softmax(output, axis=1)
        correct_prediction = tf.equal(tf.cast(tf.argmax(after_softmax, axis=1), tf.int32), y)
        total_correct = total_correct + tf.reduce_sum(tf.cast(correct_prediction, tf.float32))
    test_accuracy = total_correct/x_testing.shape[0]
    return test_accuracy.numpy(), train_accuracy.numpy()


def pre_train(x_pre_train, y_pre_train, rln, tln, learning_rate, classification_parameters):
    with tf.GradientTape() as tape:
        loss, output = compute_loss(x_pre_train, y_pre_train, rln, tln, classification_parameters)
    params = rln.trainable_variables + tln.trainable_variables
    gradients = tape.gradient(loss, params)
    for p, g in zip(params, gradients):
        p.assign(p - g * learning_rate)
    return loss, output

def get_output(x_pre_train, y_pre_train, rln, tln, classification_parameters):
    with tf.GradientTape() as tape:
        loss, output = compute_loss(x_pre_train, y_pre_train, rln, tln, classification_parameters)
    return loss, output