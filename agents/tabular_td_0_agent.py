import numpy as np
import tensorflow as tf

from agents import TabularMCAgent, capacities

class TabularTD0Agent(TabularMCAgent):
    """
    Agent implementing tabular TD(0) learning.
    """
    def set_agent_props(self):
        self.lr = self.config['lr']
        self.lr_decay_steps = self.config['lr_decay_steps']
        self.discount = self.config['discount']
        self.N0 = self.config['N0']
        self.min_eps = self.config['min_eps']
        self.initial_q_value = self.config['initial_q_value']

    def get_best_config(self, env_name=""):
        cartpolev0 = {
            'lr': 0.5 # ->.5] improve
            , 'lr_decay_steps': 30000
            , 'discount': 0.999 # ->1[ improve
            , 'N0': 10 # ->10 improve
            , 'min_eps': 0.001 # ->0.001[ improve
            , 'initial_q_value': 0
        }
        mountaincarv0 = {
            "min_eps": 0.001,
            "N0": 100,
            "lr": 0.1,
            "initial_q_value": 0,
            "discount": 1.,
            "lr_decay_steps": 100000
        }
        acrobotv1 = {
            "discount": 0.999
            , "initial_q_value": 0
            , "N0": 100
            , "min_eps": 0.11409578938939571
          }
        return {
            'CartPole-v0': cartpolev0
            , 'MountainCar-v0': mountaincarv0
            , 'Acrobot-v1': acrobotv1
        }.get(env_name, cartpolev0)

    @staticmethod
    def get_random_config(fixed_params={}):
        get_lr = lambda: 1e-2 + (.9 - 1e-2) * np.random.random(1)[0]
        get_lr_decay_steps = lambda: np.random.randint(1e3, 1e5)
        get_discount = lambda: 0.98 + (1 - 0.98) * np.random.random(1)[0]
        get_N0 = lambda: np.random.randint(1, 1e3)
        get_min_eps = lambda: 1e-4 + (2e-1 - 1e-4) * np.random.random(1)[0]
        get_initial_q_value = lambda: 0

        random_config = {
            'lr': get_lr()
            , 'lr_decay_steps': get_lr_decay_steps()
            , 'discount': get_discount()
            , 'N0': get_N0()
            , 'min_eps': get_min_eps()
            , 'initial_q_value': get_initial_q_value()
        }
        random_config.update(fixed_params)

        return random_config

    def build_graph(self, graph):
        with graph.as_default():
            tf.set_random_seed(self.random_seed)

            self.inputs_plh = tf.placeholder(tf.int32, shape=[None], name="inputs_plh")
            
            q_scope = tf.VariableScope(reuse=False, name='QValues')
            with tf.variable_scope(q_scope):
                self.Qs = tf.get_variable('Qs'
                    , shape=[self.nb_state, self.action_space.n]
                    , initializer=tf.constant_initializer(self.initial_q_value)
                    , dtype=tf.float32
                )
                tf.summary.histogram('Qarray', self.Qs)
                self.q_preds_t = tf.gather(self.Qs, self.inputs_plh)

            policy_scope = tf.VariableScope(reuse=False, name='Policy')
            with tf.variable_scope(policy_scope):
                if 'UCB' in self.config and self.config['UCB']:
                    self.actions_t, self.probs_t = capacities.tabular_UCB(
                        self.Qs, self.inputs_plh
                    )    
                else:
                    self.actions_t, self.probs_t = capacities.tabular_eps_greedy(
                        self.inputs_plh, self.q_preds_t, self.nb_state, self.env.action_space.n, self.N0, self.min_eps
                    )
                self.action_t = self.actions_t[0]
                self.q_value_t = self.q_preds_t[0][self.action_t]

            learning_scope = tf.VariableScope(reuse=False, name='Learning')
            with tf.variable_scope(learning_scope):
                self.rewards_plh = tf.placeholder(tf.float32, shape=[None], name="rewards_plh")
                self.next_states_plh = tf.placeholder(tf.int32, shape=[None], name="next_states_plh")
                self.next_actions_plh = tf.placeholder(tf.int32, shape=[None], name="next_actions_plh")

                targets_t = capacities.get_td_target(self.Qs, self.rewards_plh, self.next_states_plh, self.next_actions_plh, self.discount)
                # When boostraping, the target is non-stationnary, we need a learning rate
                self.loss, self.train_op = capacities.tabular_learning_with_lr(
                    self.lr, self.lr_decay_steps, self.Qs, self.inputs_plh, self.actions_t, targets_t
                )

            self.score_plh = tf.placeholder(tf.float32, shape=[])
            self.score_sum_t = tf.summary.scalar('score', self.score_plh)
            self.loss_plh = tf.placeholder(tf.float32, shape=[])
            self.loss_sum_t = tf.summary.scalar('loss', self.loss_plh)
            self.all_summary_t = tf.summary.merge_all()

            self.episode_id, self.inc_ep_id_op = capacities.counter("episode_id")

            # Playing part
            self.pscore_plh = tf.placeholder(tf.float32, shape=[])
            self.pscore_sum_t = tf.summary.scalar('play_score', self.pscore_plh)

        return graph

    def learn_from_episode(self, env, render=False):
        score = 0
        av_loss = []
        done = False

        obs = env.reset()
        act, state_id = self.act(obs, done)
        while not done:
            if render:
                env.render()

            next_obs, reward, done, info = env.step(act)
            next_act, next_state_id = self.act(next_obs, done)

            loss, _ = self.sess.run([self.loss, self.train_op], feed_dict={
                self.inputs_plh: [ state_id ],
                self.actions_t: [ act ],
                self.rewards_plh: [ reward ],
                self.next_states_plh: [ next_state_id ],
                self.next_actions_plh: [ next_act ],
            })

            av_loss.append(loss)
            score += reward
            obs = next_obs
            state_id = next_state_id
            act = next_act

        summary, _, episode_id = self.sess.run([self.all_summary_t, self.inc_ep_id_op, self.episode_id], feed_dict={
            self.score_plh: score,
            self.loss_plh: np.mean(av_loss),
        })
        self.sw.add_summary(summary, episode_id)

        return