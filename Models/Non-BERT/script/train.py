import torch
import torch.nn as nn
import torch.optim as optim
import sys
import time
import numpy as np
import random
from collections import Counter
from data_utils import ABSADatesetReader
from torch.utils.data import DataLoader
from sklearn.metrics import  f1_score
import argparse


from models.LSTM import LSTM
from models.CNN import CNN
from models.TD_LSTM import TD_LSTM
from models.TC_LSTM import TC_LSTM
from models.MemNet import MemNet
from models.IAN import IAN
from models.RAM import RAM
from models.ATAE_LSTM import ATAE_LSTM
from models.CABASC import CABASC


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
save_path = sys.path[0] + "/result/"
base_path = sys.path[0] + '/data/store/'


def clip_gradient(parameters, clip):
    
    return nn.utils.clip_grad_norm(parameters, clip)


def tensor_to_numpy(x):
    
    return x.data.type(torch.DoubleTensor).numpy()


class BaseExperiment:

    def __init__(self, args):
        self.args = args
        torch.manual_seed(self.args.seed)
        if self.args.device == "cuda":
            torch.cuda.set_device(self.args.gpu)
            torch.cuda.manual_seed(self.args.seed)
        np.random.seed(self.args.seed)
        random.seed(self.args.seed)
        print('> training arguments:')
        for arg in vars(args):
            print('>>> {0}: {1}'.format(arg, getattr(args, arg)))

        absa_dataset = ABSADatesetReader(dataset=args.dataset, embed_dim=args.embed_dim, max_seq_len=args.max_seq_len)
        if self.args.dev > 0.0:
            random.shuffle(absa_dataset.train_data.data)
            dev_num = int(len(absa_dataset.train_data.data) * self.args.dev)
            absa_dataset.dev_data.data = absa_dataset.train_data.data[:dev_num]
            absa_dataset.train_data.data = absa_dataset.train_data.data[dev_num:]

        

        self.train_data_loader = DataLoader(dataset=absa_dataset.train_data, batch_size=args.batch_size, shuffle=True)
        if self.args.dev > 0.0:
            self.dev_data_loader = DataLoader(dataset=absa_dataset.dev_data, batch_size=len(absa_dataset.dev_data),
                                              shuffle=False)
        self.test_data_loader = DataLoader(dataset=absa_dataset.test_data, batch_size=len(absa_dataset.test_data),
                                           shuffle=False)
        self.mdl = args.model_class(self.args, embedding_matrix=absa_dataset.embedding_matrix,
                                    aspect_embedding_matrix=absa_dataset.aspect_embedding_matrix)
        self.reset_parameters()
        self.mdl.encoder.weight.requires_grad = True
        self.mdl.encoder_aspect.weight.requires_grad = True
        self.mdl.to(device)
        self.criterion = nn.CrossEntropyLoss()

    def reset_parameters(self):
        n_trainable_params, n_nontrainable_params = 0, 0
        for p in self.mdl.parameters():
            n_params = torch.prod(torch.tensor(p.shape))
            if p.requires_grad:
                n_trainable_params += n_params
                if len(p.shape) > 1:
                    self.args.initializer(p)
            else:
                n_nontrainable_params += n_params
        print('n_trainable_params: {0}, n_nontrainable_params: {1}'.format(n_trainable_params, n_nontrainable_params))

    def select_optimizer(self):
        if self.args.optimizer == 'Adam':
            self.optimizer = optim.Adam(filter(lambda p: p.requires_grad, self.mdl.parameters()),
                                        lr=self.args.learning_rate)
        elif self.args.optimizer == 'RMS':
            self.optimizer = optim.RMSprop(filter(lambda p: p.requires_grad, self.mdl.parameters()),
                                           lr=self.args.learning_rate)
        elif self.args.optimizer == 'SGD':
            self.optimizer = optim.SGD(filter(lambda p: p.requires_grad, self.mdl.parameters()),
                                       lr=self.args.learning_rate)
        elif self.args.optimizer == 'Adagrad':
            self.optimizer = optim.Adagrad(filter(lambda p: p.requires_grad, self.mdl.parameters()),
                                           lr=self.args.learning_rate)
        elif self.args.optimizer == 'Adadelta':
            self.optimizer = optim.Adadelta(filter(lambda p: p.requires_grad, self.mdl.parameters()),
                                            lr=self.args.learning_rate)

    def load_model(self, PATH):
        # mdl_best = self.load_model(PATH)
        # best_model_state = mdl_best.state_dict()
        # model_state = self.mdl.state_dict()
        # best_model_state = {k: v for k, v in best_model_state.iteritems() if
        #                     k in model_state and v.size() == model_state[k].size()}
        # model_state.update(best_model_state)
        # self.mdl.load_state_dict(model_state)
        return torch.load(PATH)

    def train_batch(self, sample_batched):
        self.mdl.zero_grad()
        inputs = [sample_batched[col].to(device) for col in self.args.inputs_cols]
        targets = sample_batched['polarity'].to(device)
        outputs = self.mdl(inputs)
        loss = self.criterion(outputs, targets)
        loss.backward()
        clip_gradient(self.mdl.parameters(), 1.0)
        self.optimizer.step()
        return loss.data[0]

    def evaluation(self, x):
        inputs = [x[col].to(device) for col in self.args.inputs_cols]
        targets = x['polarity'].to(device)
        outputs = self.mdl(inputs)
        outputs = tensor_to_numpy(outputs)
        targets = tensor_to_numpy(targets)
        outputs = np.argmax(outputs, axis=1)
        return outputs, targets

    def metric(self, targets, outputs, save_path=None):
        dist = dict(Counter(outputs))
        
        macro_f1 = f1_score(targets, outputs, labels=[0, 1, 2], average='macro')
        
        result = {'macro_f1': macro_f1}
        
        if save_path is not None:
            f_to = open(save_path, 'w')
            f_to.write("lr: {}\n".format(self.args.learning_rate))
            f_to.write("batch_size: {}\n".format(self.args.batch_size))
            f_to.write("opt: {}\n".format(self.args.optimizer))
            f_to.write("max_sentence_len: {}\n".format(self.args.max_seq_len))
            f_to.write("end params -----------------------------------------------------------------\n")
            for key in result.keys():
                f_to.write("{}: {}\n".format(key, result[key]))
            f_to.write("end metrics -----------------------------------------------------------------\n")
            for i in range(len(outputs)):
                f_to.write("{}: {},{}\n".format(i, outputs[i], targets[i]))
            f_to.write("end ans -----------------------------------------------------------------\n")
            f_to.close()
        return result

    def train(self):
        best_f1 = 0.0
        best_result = None
        global_step = 0
        self.select_optimizer()
        for epoch in range(self.args.num_epoch):
            losses = []
            self.mdl.train()
            t0 = time.clock()
            for i_batch, sample_batched in enumerate(self.train_data_loader):
                global_step += 1
                loss = self.train_batch(sample_batched)
                losses.append(loss)
            t1 = time.clock()
            self.mdl.eval()
            if self.args.dev > 0.0:
                outputs, targets = None, None
                with torch.no_grad():
                    for d_batch, d_sample_batched in enumerate(self.dev_data_loader):
                        output, target = self.evaluation(d_sample_batched)
                        if outputs is None:
                            outputs = output
                        else:
                            outputs = np.concatenate((outputs, output))

                        if targets is None:
                            targets = target
                        else:
                            targets = np.concatenate((targets, target))
                    result = self.metric(targets=targets, outputs=outputs)
                    if result['macro_f1'] > best_f1:
                        best_f1 = result['macro_f1']
                        PATH = save_path + 'models/{}_{}_{}_{}_{}_{}_{}_{}_{}.model'.format(self.args.model_name,
                                                                                            self.args.dataset,
                                                                                            self.args.optimizer,
                                                                                            self.args.learning_rate,
                                                                                            self.args.max_seq_len,
                                                                                            self.args.dropout,
                                                                                            self.args.softmax,
                                                                                            self.args.batch_size,
                                                                                            self.args.dev)
                        torch.save(self.mdl.state_dict(), PATH)
                        best_result = result
            else:
                outputs, targets = None, None
                with torch.no_grad():
                    for t_batch, t_sample_batched in enumerate(self.test_data_loader):
                        output, target = self.evaluation(t_sample_batched)
                        if outputs is None:
                            outputs = output
                        else:
                            outputs = np.concatenate((outputs, output))
                        if targets is None:
                            targets = target
                        else:
                            targets = np.concatenate((targets, target))
                    result = self.metric(targets=targets, outputs=outputs)
                    if result['macro_f1'] > best_f1:
                        best_f1 = result['macro_f1']
                        PATH = save_path + 'models/{}_{}_{}_{}_{}_{}_{}_{}_{}.model'.format(self.args.model_name,
                                                                                            self.args.dataset,
                                                                                            self.args.optimizer,
                                                                                            self.args.learning_rate,
                                                                                            self.args.max_seq_len,
                                                                                            self.args.dropout,
                                                                                            self.args.softmax,
                                                                                            self.args.batch_size,
                                                                                            self.args.dev)
                        torch.save(self.mdl.state_dict(), PATH)
                        best_result = result
            print("[Epoch {}] Train Loss={} Test macro_f1={} T={}s".format(epoch, np.mean(losses), result['macro_f1'], t1 - t0))
        return best_result

    def test(self):
        PATH = save_path + 'models/{}_{}_{}_{}_{}_{}_{}_{}_{}.model'.format(self.args.model_name, self.args.dataset,
                                                                            self.args.optimizer,
                                                                            self.args.learning_rate,
                                                                            self.args.max_seq_len, self.args.dropout,
                                                                            self.args.softmax, self.args.batch_size,
                                                                            self.args.dev)
        ans_file = save_path + 'ans/{}_{}_{}_{}_{}_{}_{}_{}_{}.txt'.format(self.args.model_name, self.args.dataset,
                                                                           self.args.optimizer, self.args.learning_rate,
                                                                           self.args.max_seq_len, self.args.dropout,
                                                                           self.args.softmax, self.args.batch_size,
                                                                           self.args.dev)
        self.mdl.load_state_dict(self.load_model(PATH))
        self.mdl.eval()
        outputs, targets = None, None
        with torch.no_grad():
            for t_batch, t_sample_batched in enumerate(self.test_data_loader):
                output, target = self.evaluation(t_sample_batched)
                if outputs is None:
                    outputs = output
                else:
                    outputs = np.concatenate((outputs, output))

                if targets is None:
                    targets = target
                else:
                    targets = np.concatenate((targets, target))
        result = self.metric(targets=targets, outputs=output, save_path=ans_file)
        print("macro_f1:{}".format(result['macro_f1']))
        return result


if __name__ == '__main__':
    # Hyper Parameters
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_name', default='LSTM', type=str)
    parser.add_argument('--dataset', default='twitter', type=str,
                        help='restaurants14, laptop14')
    parser.add_argument('--optimizer', default='Adam', type=str)
    parser.add_argument('--initializer', default='xavier_uniform_', type=str)
    parser.add_argument('--learning_rate', default=0.001, type=float)
    parser.add_argument('--num_epoch', default=100, type=int)
    parser.add_argument('--batch_size', default=16, type=int)
    parser.add_argument('--gpu', default=0, type=int)
    parser.add_argument('--embed_dim', default=300, type=int)
    parser.add_argument('--hidden_dim', default=300, type=int)
    parser.add_argument('--max_seq_len', default=80, type=int)
    parser.add_argument('--polarities_dim', default=3, type=int)
    parser.add_argument('--kernel_num', default=100, type=int)
    parser.add_argument('--kernel_sizes', default=[3, 4, 5], nargs='+', type=int)
    parser.add_argument('--hops', default=3, type=int)
    parser.add_argument('--seed', default=111, type=int)
    parser.add_argument('--batch_normalizations', action="store_true", default=False)
    parser.add_argument('--softmax', action="store_true", default=False)
    parser.add_argument('--dev', default=0.20, type=float)
    parser.add_argument('--dropout', default=0.50, type=float)

    args = parser.parse_args()
    model_classes = {
        'CNN': CNN,
        'TD_LSTM': TD_LSTM,
        'LSTM': LSTM,
        'MemNet': MemNet,
        'IAN': IAN,
        'RAM': RAM,
        'ATAE_LSTM': ATAE_LSTM,
        'TC_LSTM': TC_LSTM,
        'CABASC': CABASC,
        
    }
    input_colses = {
        'LSTM': ['text_raw_indices'],
        'CNN': ['text_raw_indices'],
        'ATAE_LSTM': ['text_raw_indices', 'aspect_indices'],
        'TD_LSTM': ['text_left_with_aspect_indices', 'text_right_with_aspect_indices'],
        'TC_LSTM': ['text_left_with_aspect_indices', 'text_right_with_aspect_indices', 'aspect_indices'],
        'IAN': ['text_raw_indices', 'aspect_indices'],
        'MemNet': ['text_raw_without_aspect_indices', 'aspect_indices', 'text_left_with_aspect_indices'],
        'RAM': ['text_raw_indices', 'aspect_indices'],
        'CABASC': ['text_raw_indices', 'aspect_indices', 'text_left_with_aspect_indices',
                   'text_right_with_aspect_indices'],
        
    }
    initializers = {
        'xavier_uniform_': torch.nn.init.xavier_uniform_,
        'xavier_normal_': torch.nn.init.xavier_normal,
        'orthogonal_': torch.nn.init.orthogonal_,
    }
    args.model_class = model_classes[args.model_name]
    args.inputs_cols = input_colses[args.model_name]
    args.initializer = initializers[args.initializer]
    args.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    # args.batch_normalizations = False
    exp = BaseExperiment(args)
    result = exp.train()
    exp.test()
