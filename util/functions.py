import torch
import torch.nn as nn
from torch.autograd import Variable  
import numpy as np
import editdistance as ed

# CreateOnehotVariable function
# *** DEV NOTE : This is a workaround to achieve one, I'm not sure how this function affects the training speed ***
# This is a function to generate an one-hot encoded tensor with given batch size and index
# Input : input_x which is a Tensor or Variable with shape [batch size, timesteps]
#         encoding_dim, the number of classes of input
# Output: onehot_x, a Variable containing onehot vector with shape [batch size, timesteps, encoding_dim]
def CreateOnehotVariable( input_x, encoding_dim=63):
    if type(input_x) is Variable:
        input_x = input_x.data 
    input_type = type(input_x)
    batch_size = input_x.size(0)
    time_steps = input_x.size(1)
    input_x = input_x.unsqueeze(2).type(torch.LongTensor)
    onehot_x = Variable(torch.LongTensor(batch_size, time_steps, encoding_dim).zero_().scatter_(-1,input_x,1)).type(input_type)
    
    return onehot_x

# TimeDistributed function
# This is a pytorch version of TimeDistributed layer in Keras I wrote
# The goal is to apply same module on each timestep of every instance
# Input : module to be applied timestep-wise (e.g. nn.Linear)
#         3D input (sequencial) with shape [batch size, timestep, feature]
# output: Processed output      with shape [batch size, timestep, output feature dim of input module]
def TimeDistributed(input_module, input_x):
    batch_size = input_x.size(0)
    time_steps = input_x.size(1)
    reshaped_x = input_x.contiguous().view(-1, input_x.size(-1))
    output_x = input_module(reshaped_x)
    return output_x.view(batch_size,time_steps,-1)

# LetterErrorRate function
# Merge the repeated prediction and calculate editdistance of prediction and ground truth
def LetterErrorRate(pred_y,true_y):
    ed_accumalate = []
    for p,t in zip(pred_y,true_y):
        compressed_t = []
        compressed_p = []
        compressed_t = [w for w in t if (w!=1 and w!=0)]
        p_reach_end = False
        for p_w,t_w in zip(p,t):
            if p_w == 1:
                break
            compressed_p.append(p_w)
        ed_accumalate.append(ed.eval(compressed_p,compressed_t)/len(compressed_t))
    return ed_accumalate

def batch_iterator(batch_data, batch_label, listener, speller, optimizer, tf_rate, is_training, **kwargs):
    bucketing = kwargs['bucketing']
    use_gpu = kwargs['use_gpu']
    max_label_len = kwargs['max_label_len']
    output_class_dim = kwargs['output_class_dim']
    # Load data
    if bucketing:
        batch_data = batch_data.squeeze(dim=0)
        batch_label = batch_label.squeeze(dim=0)
    current_batch_size = len(batch_data)
    batch_data = Variable(batch_data).type(torch.FloatTensor)
    batch_label = Variable(batch_label, requires_grad=False)
    objective = nn.CrossEntropyLoss(ignore_index=0)
    if use_gpu:
        batch_data = batch_data.cuda()
        batch_label = batch_label.cuda()
        objective = objective.cuda()
    # Forwarding
    optimizer.zero_grad()
    listner_feature = listener(batch_data)
    if is_training:
        raw_pred_seq, attention_record = speller(listner_feature,ground_truth=batch_label,teacher_force_rate=tf_rate)
    else:
        raw_pred_seq, attention_record = speller(listner_feature,ground_truth=None,teacher_force_rate=0)

    pred_y = torch.cat([torch.unsqueeze(each_y,1) for each_y in raw_pred_seq],1).view(-1,output_class_dim)
    true_y = torch.max(batch_label,dim=2)[1].view(-1)

    loss = objective(pred_y,true_y)

    if is_training:
        loss.backward()
        optimizer.step()

    batch_loss = loss.cpu().data.numpy()
    # variable -> numpy before sending into LER calculator
    batch_ler = LetterErrorRate(torch.max(pred_y,dim=1)[1].cpu().data.numpy().reshape(current_batch_size,max_label_len),
                                true_y.cpu().data.numpy().reshape(current_batch_size,max_label_len))
    return batch_loss, batch_ler







