import tensorflow as tf
import numpy as np
import datetime
import os
import json


from experiments.exp4_2.omniglot_model import mrcl_omniglot, get_eval_data_by_classes, evaluate_classification_mrcl
from datasets.tf_datasets import load_omniglot
from parameters import classification_parameters

dataset = "omniglot"
background_data, evaluation_data = load_omniglot(dataset, verbose=1)
evaluation_training_data, evaluation_test_data = get_eval_data_by_classes(evaluation_data)

current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
train_log_dir = 'logs/classification/gradient_tape/' + current_time + '/train'
train_summary_writer = tf.summary.create_file_writer(train_log_dir)

rln, tln = mrcl_omniglot(classes=200)

try:
    os.stat("evaluation_results_scratch_omniglot")
except:
    os.mkdir("evaluation_results_scratch_omniglot")

points = [10, 50, 75, 100, 150, 200]
for point in points:
    original_rln, original_tln = mrcl_omniglot(classes=point)
    lrs = [0.3, 0.1, 0.03, 0.01, 0.003, 0.001, 0.0003, 0.0001, 0.00003, 0.00001]
    test_accuracy_results = []
    train_accuracy_results = []
    for lr in lrs:
        classification_parameters["online_learning_rate"] = lr
        rln, tln = mrcl_omniglot(classes=point)
        tln.set_weights(original_tln.get_weights())
        rln.set_weights(original_rln.get_weights())
        test_accuracy, train_accuracy = evaluate_classification_mrcl(evaluation_training_data, evaluation_test_data,
                                                                     rln, tln, point, classification_parameters)
        test_accuracy_results.append(test_accuracy)
        train_accuracy_results.append(train_accuracy)
        print(f"Learning rate {lr}, test accuracy {test_accuracy}, train accuracy {train_accuracy}")

    test_lr = lrs[np.argmax(np.array(test_accuracy_results))]
    train_lr = lrs[np.argmax(np.array(train_accuracy_results))]
    print(
        f"Number of classes {point}. Best testing learning rate is {test_lr} and best training learning rate is {train_lr}.")
    test_accuracy_results = []
    train_accuracy_results = []

    print(f"Starting 50 iterations of evaluation testing with learning rate {test_lr}.")
    for _ in range(50):
        classification_parameters["online_learning_rate"] = test_lr
        rln, tln = mrcl_omniglot(classes=point)
        tln.set_weights(original_tln.get_weights())
        rln.set_weights(original_rln.get_weights())
        test_accuracy, _ = evaluate_classification_mrcl(evaluation_training_data, evaluation_test_data, rln, tln, point,
                                                        classification_parameters)
        test_accuracy_results.append(str(test_accuracy))
    lr_str = f"{test_lr}".replace(".", "_")
    with open(f"evaluation_results_scratch_omniglot/mrcl_omniglot_testing_{point}.json",
              'w') as f:  # writing JSON object
        json.dump(test_accuracy_results, f)

    print(f"Starting 50 iterations of evaluation training with learning rate {train_lr}.")
    for _ in range(50):
        classification_parameters["online_learning_rate"] = train_lr
        rln, tln = mrcl_omniglot(classes=point)
        tln.set_weights(original_tln.get_weights())
        rln.set_weights(original_rln.get_weights())
        _, train_accuracy = evaluate_classification_mrcl(evaluation_training_data, evaluation_test_data, rln,
                                                         tln, point, classification_parameters)
        train_accuracy_results.append(str(train_accuracy))
    lr_str = f"{train_lr}".replace(".", "_")
    with open(f"evaluation_results_scratch_omniglot/mrcl_omniglot_training_{point}.json",
              'w') as f:  # writing JSON object
        json.dump(train_accuracy_results, f)
