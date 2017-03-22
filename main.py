import gym, os, time, json
import tensorflow as tf
import numpy as np

from agents import make_agent
from hyperband import Hyperband, make_get_params, make_run_params

dir = os.path.dirname(os.path.realpath(__file__))

flags = tf.app.flags

# Hyperband
flags.DEFINE_boolean('hyperband', False, 'Perform a hyperband search of hyperparameters')

# Agent
flags.DEFINE_string('agent_name', 'DeepQAgent', 'Name of the agent')
flags.DEFINE_integer('max_iter', 2000, 'Number of training step')
flags.DEFINE_float('lr', 1e-3, 'Learning rate')
flags.DEFINE_float('nb_units', 40, 'Number of hidden units in Deep learning agents')

# Policy
flags.DEFINE_integer('N0', 100, 'Offset used in the decay algorithm of espilon')
flags.DEFINE_float('min_eps', 1e-2, 'Limit after which the decay stops')

# Experience replay
flags.DEFINE_float('er_lr', 1e-3, 'Experience replay learning rate')
flags.DEFINE_integer('er_every', 20, 'If the model can handle experience replay, use it every n episode_id')
flags.DEFINE_integer('er_batch_size', 64, 'Batch size of the experience replay learning')
flags.DEFINE_integer('er_epoch_size', 50, 'Number of sampled contained in an epoch of experience replay')
flags.DEFINE_integer('er_rm_size', 20000, 'Size of the replay memory buffer')

# Environment
flags.DEFINE_string('env_name', 'CartPole-v0', 'The name of gym environment to use')
flags.DEFINE_boolean('debug', False, 'Debug mode')

flags.DEFINE_string('result_dir', dir + '/results/' + flags.FLAGS.env_name + '/' + flags.FLAGS.agent_name + '/' + str(int(time.time())), 'Name of the directory to store/log the agent (if it exists, the agent will be loaded from it)')

flags.DEFINE_boolean('play', False, 'Load an agents for playing')
# flags.DEFINE_integer('random_seed', 123, 'Value of random seed')

def main(_):
    config = flags.FLAGS.__flags.copy()
    if config['hyperband']:
        print('Starting hyperband search')
        config['result_dir_prefix'] = dir + '/results/hyperband/' + str(int(time.time()))
        get_params = make_get_params(config)
        run_params = make_run_params(config['env_name'], config['agent_name'])

        hb = Hyperband( get_params, run_params )
        results = hb.run()
        with open(config['result_dir_prefix'] + '/hb_results.json', 'w') as f:
            json.dump(results, f)
    else:
        # if os.path.isfile(config['result_dir'] + '/config.json'):
        #     print('Warning: loading config from file: %s' % (config['result_dir'] + '/config.json'))
        #     with open(config['result_dir'] + '/config.json', 'r') as f:
        #         config = json.load(f)
        print(config)

        env = gym.make(config['env_name'])
        agent = make_agent(config, env)

        if config['play']:
            agent.play(env)
        else:
            agent.train()
            agent.save()


if __name__ == '__main__':
  tf.app.run()