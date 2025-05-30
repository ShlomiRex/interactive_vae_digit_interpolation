import torch
import torch.nn as nn
import math
from einops import rearrange

class VariationalAutoencoder(nn.Module):
    def __init__(self, input_dim, hidden_dim, latent_dim, device='cpu'):
        super(VariationalAutoencoder, self).__init__()
        self.to(device)
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.device = device

        self.image_width = int(math.sqrt(input_dim))
        self.image_height = int(math.sqrt(input_dim))

        self.__setup_encoder()
        self.__setup_decoder()
    
    def __setup_encoder(self):
        self.enc_fc1 = nn.Linear(self.input_dim, self.hidden_dim).to(self.device)
        self.enc_fc2 = nn.Linear(self.hidden_dim, self.hidden_dim).to(self.device)

        self.relu = nn.ReLU().to(self.device)

        # Now we have two layers for each vector in latent space (going from hidden_dim to latent_dim)
        self.fc_mu = nn.Linear(self.hidden_dim, self.latent_dim).to(self.device)  # Mean vector
        self.fc_logvar = nn.Linear(self.hidden_dim, self.latent_dim).to(self.device)  # Log-variance vector

    def __setup_decoder(self):
        self.dec_fc1 = nn.Linear(self.latent_dim, self.hidden_dim)
        self.dec_fc2 = nn.Linear(self.hidden_dim, self.hidden_dim)
        self.dec_fc3 = nn.Linear(self.hidden_dim, self.input_dim)
    
    def encode(self, x):
        x = rearrange(x, 'b c h w -> b (c h w)') # Flatten the input
        x = self.relu(self.enc_fc1(x))
        x = self.relu(self.enc_fc2(x))

        mean = self.fc_mu(x)
        log_var = self.fc_logvar(x)

        # Here we don't return x, we return mean and log_var, this is different to AE
        return mean, log_var
    
    def decode(self, latent):
        x = self.relu(self.dec_fc1(latent))
        x = self.relu(self.dec_fc2(x))

        x_hat = torch.sigmoid(self.dec_fc3(x))

        x_hat = rearrange(x_hat, 'b (c h w) -> b c h w', c=1, h=self.image_width, w=self.image_height) # Reshape the output

        return x_hat
    
    def reparameterization(self, mean, var):
        """
        Variance is exponential of log_var
        """
        epsilon = torch.randn_like(var).to(self.device)
        mean = mean.to(self.device)
        var = var.to(self.device)

        z = mean + var * epsilon
        return z


    def forward(self, x):
        assert x.shape[-3:] == (1, 28, 28)

        x.to(self.device)

        # Encode - instead of latent vector we get mean and log_var (look at image!)
        mean, log_var = self.encode(x)

        # Here is the magic of VAE
        z = self.reparameterization(mean, torch.exp(0.5 * log_var))
        
        # Decode
        x_reconstructed = self.decode(z)

        # Return x hat
        return x_reconstructed, mean, log_var

class MNIST_VAE(VariationalAutoencoder):
    def __init__(self):
        super(MNIST_VAE, self).__init__(input_dim=1*28*28, hidden_dim=400, latent_dim=200)
class InterpolationModel(nn.Module):
    def __init__(self, vae_model):
        super(InterpolationModel, self).__init__()
        self.vae = vae_model
    
    def forward(self, input_img1: torch.Tensor, input_img2: torch.Tensor, interpolation: float) -> torch.Tensor:
        # Check if the input images size
        assert input_img1.shape == (1, 28, 28), "Input image 1 must be of shape (1, 28, 28)"
        assert input_img2.shape == (1, 28, 28), "Input image 2 must be of shape (1, 28, 28)"

        # Add batch dimension
        input_img1 = rearrange(input_img1, 'c h w -> 1 c h w') # Add batch dimension
        input_img2 = rearrange(input_img2, 'c h w -> 1 c h w') # Add batch dimension

        # Encode the two images
        mean1, log_var1 = self.vae.encode(input_img1)
        mean2, log_var2 = self.vae.encode(input_img2)

        # Reparameterization trick for both images
        z1 = self.vae.reparameterization(mean1, torch.exp(0.5 * log_var1))
        z2 = self.vae.reparameterization(mean2, torch.exp(0.5 * log_var2))

        # Interpolate between the two latent vectors
        latent_vector = (1 - interpolation) * z1 + interpolation * z2 # Linear interpolation

        # Decode interpolation to image
        interpolated_image = self.vae.decode(latent_vector)

        return interpolated_image.squeeze(0) # Remove the batch dimension only (keep channel dimension 1)

class MNISTInterpolationModel(InterpolationModel):
    def __init__(self, vae_model_path: str, device='cpu'):
        # Load the variational autoencoder model
        my_vae = MNIST_VAE().to(device).eval()


        state_dict = torch.load(vae_model_path, map_location=device)
        # Remove 'vae.' prefix from all keys
        # Because we wrap the VAE model in new class (MNISTInterpolationModel) and save it, the keys in the state_dict have 'vae.' prefix
        new_state_dict = {k.replace("vae.", ""): v for k, v in state_dict.items()}
        # Load the state dict into the model
        my_vae.load_state_dict(new_state_dict)

        # Load the interpolation model
        interpolation_model = InterpolationModel(my_vae).to(device).eval()

        super(MNISTInterpolationModel, self).__init__(interpolation_model.vae)

def load_interpolation_model():
    print("Loading MNISTInterpolationModel...")
    device = 'cpu'
    interpolation_model = MNISTInterpolationModel("vae_model.pth").to(device).eval()
    interpolation_model.load_state_dict(torch.load("interpolation_model.pth", map_location=device))

def save_interpolation_model():
    print("Saving MNISTInterpolationModel...")
    device = 'cpu'
    interpolation_model = MNISTInterpolationModel("vae_model.pth").to(device).eval()
    torch.save(interpolation_model.state_dict(), "interpolation_model.pth")

if __name__ == "__main__":
    save_interpolation_model()
    load_interpolation_model()
