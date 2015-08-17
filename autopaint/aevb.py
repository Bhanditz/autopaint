import autograd.numpy as np
from autograd import value_and_grad
from autograd.util import check_grads, quick_grad_check
from autopaint.util import load_mnist, neg_kl_diag_normal,build_logprob_mvn
from autopaint.neuralnet import one_hot, train_nn, make_nn_funs,make_batches, make_gaussian_nn_funs
from plotting import plot_density
import autograd.numpy.random as npr
from autopaint.optimizers import adam_mini_batch
import pickle
import time

def lower_bound(weights,encode,decode_log_like,N_weights_enc,train_images,samples_per_image,latent_dimensions,rs):
    enc_w = weights[0:N_weights_enc]
    dec_w = weights[N_weights_enc:len(weights)]
    (mus,log_sigs) = encode(enc_w,train_images)
    sigs = np.exp(log_sigs)
    noise = rs.randn(samples_per_image*train_images.shape[0],latent_dimensions)
    Z_samples = mus + sigs*noise
    assert Z_samples.shape == (train_images.shape[0]*samples_per_image,latent_dimensions)
    train_images_repeat = np.repeat(train_images,samples_per_image,axis=0)
    mean_log_prob = decode_log_like(dec_w,Z_samples,train_images_repeat)
    kl_vect = neg_kl_diag_normal(mus,sigs)
    print "ll average", mean_log_prob.value
    print "kl average", np.mean(kl_vect).value
    return mean_log_prob+np.mean(kl_vect)

def build_encoder(enc_layers):
    L2_reg = 0
    N_weights, predict_fun, log_likelihood = make_gaussian_nn_funs(enc_layers, L2_reg)
    return N_weights,predict_fun

def build_gaussian_decoder(dec_layers):
    L2_reg = 0
    N_weights, predict_fun, log_likelihood = make_gaussian_nn_funs(dec_layers,L2_reg)
    return N_weights, predict_fun,log_likelihood

def run_aevb(train_images):
    t0 = time.time()

    #Create aevb function
    # Training parameters
    param_scale = 0.1
    samples_per_image = 1
    latent_dimensions = 10
    hidden_units = 50
    D = train_images.shape[1]

    enc_layers = [D, hidden_units, 2*latent_dimensions]
    dec_layers = [latent_dimensions, hidden_units, D*2]

    N_weights_enc,encoder = build_encoder(enc_layers)
    N_weights_dec,decoder, decoder_log_like = build_gaussian_decoder(dec_layers)

    #Optimize aevb
    batch_size = 256
    num_epochs = 100
    rs = npr.RandomState([0])
    enc_w = rs.randn(N_weights_enc) * param_scale
    dec_w = rs.randn(N_weights_dec) * param_scale

    weights = np.concatenate((enc_w,dec_w))

    def lower_bound_test(weights):
        rs = npr.RandomState(0)
        return lower_bound(weights,encoder,decoder_log_like,N_weights_enc,train_images,samples_per_image,latent_dimensions,rs)

    batch_idxs = make_batches(train_images.shape[0], batch_size)

    def batch_value_and_grad(weights,idxs):
        def batch_lower_bound(weights):
            return lower_bound(weights,encoder,decoder_log_like,N_weights_enc,train_images[idxs],samples_per_image,latent_dimensions,rs)
        #TODO:Make it so we don't have to recompute gradient at each iter?
        val_and_grad_func = value_and_grad(batch_lower_bound)
        return val_and_grad_func(weights)

    def print_ml(ml,weights):
        print "log marginal likelihood:", ml

    final_params, final_value = adam_mini_batch(batch_value_and_grad,weights,batch_idxs,num_epochs,callback=print_ml)

    #Generate samples
    num_samples = 1000
    z = rs.randn(num_samples,latent_dimensions)
    muSamples,log_sig_samples = decoder(dec_w,z)
    sig_samples = np.exp(log_sig_samples)
    noise = rs.randn(num_samples,D)
    samples = muSamples+sig_samples*noise
    print 'empirical mean', np.mean(samples,axis=0)
    print 'empirical cov', np.cov((samples.T))
    plot_density(samples, "aevb_approximating_dist.png")

    t1 = time.time()
    print "total runtime", t1-t0


def load_and_pickle_mnist():
    mnist_data = load_mnist()
    with open('mnist_data.pkl', 'w') as f:
        pickle.dump(mnist_data, f, 1)

if __name__ == '__main__':
    # # load_and_pickle_mnist()
    # with open('mnist_data.pkl') as f:
    #     N_data, train_images, train_labels, test_images, test_labels = pickle.load(f)
    # #

    train_images = np.random.multivariate_normal(np.zeros(2),np.array([[1,.9],[.9,1]]),1000)
    run_aevb(train_images)