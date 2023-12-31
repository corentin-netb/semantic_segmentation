import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.datasets import VOCSegmentation
import random
import logging
import os
import wandb


class SemanticSegmentationDataset:
    def __init__(self, root, year, image_set, transform=None, batch_size=64, shuffle=True, seed=42):
        random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)

        self.dataset = VOCSegmentation(
            root=root, year=year, image_set=image_set, download=True, transform=transform)
        self.loader = DataLoader(
            self.dataset, batch_size=batch_size, shuffle=shuffle)

    def __getitem__(self, idx):
        # Get the image and segmentation mask at the given index
        img, mask = self.dataset[idx]
        # Apply any additional transformations if needed
        if self.dataset.transform is not None:
            img, mask = self.dataset.transform(img, mask)
        return img, mask

    def plot(self, model):
        # Use DataLoader to get a batch
        data_iterator = iter(self.loader)
        img, mask = next(data_iterator)
        prediction = model(img)
        # Display the image, ground truth mask, and predicted mask
        plt.figure(figsize=(12, 4))
        plt.subplot(1, 3, 1)
        plt.imshow(img[0].permute(1, 2, 0))  # Assuming img is a PyTorch tensor
        plt.title('Image')
        plt.subplot(1, 3, 2)
        plt.imshow(mask[0])  # Assuming mask is a PyTorch tensor
        plt.title('Ground Truth Mask')
        plt.subplot(1, 3, 3)
        plt.imshow(prediction[0])  # Assuming prediction is a PyTorch tensor
        plt.title('Predicted Mask')
        plt.show()


class UNet(nn.Module):
    # Your implementation here
    def __init__():
        print("TODO")


class SemanticSegmentationTrainer:
    def __init__(self, model, train_loader, val_loader, criterion, optimizer, num_epochs=10, patience=5, log_dir='logs'):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.criterion = criterion
        self.optimizer = optimizer
        self.num_epochs = num_epochs
        self.patience = patience
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        self.log_dir = log_dir

        # Create the log directory if it doesn't exist
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        self.early_stopping_counter = 0
        self.best_val_loss = float('inf')

    def save_checkpoint(self, epoch, model_state, optimizer_state, train_loss, val_loss):
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': model_state,
            'optimizer_state_dict': optimizer_state,
            'train_loss': train_loss,
            'val_loss': val_loss
        }
        checkpoint_path = os.path.join(
            self.log_dir, f'checkpoint_epoch_{epoch}.pt')
        torch.save(checkpoint, checkpoint_path)
        self.logger.info(f"Checkpoint saved at epoch {epoch}")

    def early_stopping(self, val_loss):
        if val_loss < self.best_val_loss:
            self.best_val_loss = val_loss
            self.early_stopping_counter = 0
        else:
            self.early_stopping_counter += 1

        return self.early_stopping_counter >= self.patience

    def train(self):
        for epoch in range(self.num_epochs):
            self.model.train()
            total_loss = 0

            for images, masks in self.train_loader.loader:
                self.optimizer.zero_grad()
                outputs = self.model(images)
                loss = self.criterion(outputs, masks)
                loss.backward()
                self.optimizer.step()

                total_loss += loss.item()

            avg_loss = total_loss / len(self.train_loader.loader)
            self.logger.info(f'Training Loss at epoch {epoch}: {avg_loss}')

            # Validation
            self.model.eval()
            total_val_loss = 0

            with torch.no_grad():
                for val_images, val_masks in self.val_loader.loader:
                    val_outputs = self.model(val_images)
                    val_loss = self.criterion(val_outputs, val_masks)
                    total_val_loss += val_loss.item()

            avg_val_loss = total_val_loss / len(self.val_loader.loader)
            self.logger.info(
                f'Validation Loss at epoch {epoch}: {avg_val_loss}')

            # log on w and b
            self.log_to_wandb(epoch, avg_loss, avg_val_loss)

            # Early stopping check
            if self.early_stopping(avg_val_loss):
                self.logger.info(
                    f'Early stopping at epoch {epoch} due to no improvement in validation loss.')
                break

            # Save checkpoint
            self.save_checkpoint(epoch, self.model.state_dict(
            ), self.optimizer.state_dict(), avg_loss, avg_val_loss)

    def log_to_wandb(self, epoch, train_loss, val_loss):
        wandb.log(
            {"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})


class SemanticSegmentationPipeline:
    def __init__(self, root='./data', year='2012', train_batch_size=64, val_batch_size=64, num_epochs=10, seed=42, log_dir='logs'):
        self.root = root
        self.year = year
        self.train_batch_size = train_batch_size
        self.val_batch_size = val_batch_size
        self.num_epochs = num_epochs
        self.seed = seed
        self.log_dir = log_dir

    def run(self):
        wandb.init()
        wandb.config.update({
            "root": self.root,
            "year": self.year,
            "train_batch_size": self.train_batch_size,
            "val_batch_size": self.val_batch_size,
            "num_epochs": self.num_epochs,
            "seed": self.seed,
            "log_dir": self.log_dir
        })
        transform = transforms.Compose([
            transforms.Resize((224, 224, 3)),
            transforms.ToTensor(),
        ])

        train_dataset = SemanticSegmentationDataset(root=self.root, year=self.year, image_set='train',
                                                    transform=transform, batch_size=self.train_batch_size,
                                                    shuffle=True, seed=self.seed)
        val_dataset = SemanticSegmentationDataset(root=self.root, year=self.year, image_set='val',
                                                  transform=transform, batch_size=self.val_batch_size,
                                                  shuffle=False, seed=self.seed)

        # TODO : implement model
        model = UNet()  # Initialize your model
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.SGD(model.parameters(), lr=0.01,
                              momentum=0.9, weight_decay=0.0005)

        trainer = SemanticSegmentationTrainer(
            model, train_dataset, val_dataset, criterion, optimizer, self.num_epochs, self.log_dir)
        trainer.train()


if __name__ == "__main__":
    wandb.init(project='semantic-segmentation')
    pipeline = SemanticSegmentationPipeline()
    pipeline.run()
    wandb.finish()
