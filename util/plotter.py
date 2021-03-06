from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from datasets.synth_datasets import gen_tasks, gen_sine_data


def visualize(representation, save_name=None):
    """
    Visualize the representation (weights) of a layer for omniglot (fig.5 in paper)
    :param representation: last layer's weights of RLN as numpy array
    """
    representation = representation.reshape((32, 72))
    scaler = MinMaxScaler()
    scaler = scaler.fit(representation)
    representation = scaler.transform(representation)
    plt.axis('off')
    pos = plt.imshow(representation, cmap="YlGn")

    divider = make_axes_locatable(plt.gca())
    cax = divider.append_axes("right", size="5%", pad=0.05)
    plt.gcf().colorbar(pos, cax=cax)
    if save_name is not None:
        plt.savefig(save_name, bbox_inches='tight')
    plt.show()




def plot_random_isw(n_fun_to_plot=2):
    """
    Plot some randomly generated incremental sine waves functions.
    :param n_fun_to_plot: number of functions to plot. Max 10.
    """
    tasks = gen_tasks(10)
    x_traj, y_traj, _, _ = gen_sine_data(tasks)

    for i in range(n_fun_to_plot):
        plt.scatter(x_traj[i][0][:][:, 0], y_traj[i][0][:])

    plt.grid()
    plt.show()


def plot_error_bars(results):
    """
    Plot
    :return:
    """

    # for run in results:
    #     x_sequences = []
    #     for task_id, loss_res in run.items():
    #         pass

    # plt.bar(x_sequences, )
    plt.yaxis.grid(True)

    # Save the figure and show
    plt.tight_layout()
    plt.savefig('bar_plot_with_error_bars.png')
    plt.show()

# plot_random_isw(n_fun_to_plot=5)
