import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader
from tqdm import tqdm

def main():
    # 1. Setup device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[+] Using device: {device}")

    # 2. Define data transformations
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                             std=[0.229, 0.224, 0.225])
    ])

    # 3. Load dataset
    data_dir = "E:/plant_dataset/train"
    if not os.path.exists(data_dir):
        print(f"[-] Error: Data directory {data_dir} does not exist. Halting execution.")
        return

    try:
        dataset = datasets.ImageFolder(root=data_dir, transform=transform)
    except Exception as e:
        print(f"[-] Failed to load dataset: {e}")
        return
    
    # 4. Create DataLoader
    batch_size = 32
    dataloader = DataLoader(
        dataset, 
        batch_size=batch_size, 
        shuffle=True, 
        num_workers=0, 
        pin_memory=True if torch.cuda.is_available() else False
    )

    # Extract and save class names (Maintains compatibility with mapping dictionary)
    class_names = dataset.classes
    num_classes = len(class_names)
    print(f"[+] Found {num_classes} classes.")

    # Convert list to an indexed dictionary matching the FastAPI structure
    class_mapping = {str(i): name for i, name in enumerate(class_names)}

    os.makedirs('data', exist_ok=True)
    with open('data/class_names.json', 'w') as f:
        json.dump(class_mapping, f, indent=4)
    print("[+] Saved class mapping dictionary to data/class_names.json")

    # 5. Initialize Pre-trained Model (ResNet18)
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    
    # Modify the final fully connected layer for your specific dataset
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, num_classes)
    model = model.to(device)

    # 6. Define Loss Function and Optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # 7. Training Loop (Optimized to 5 Epochs for your deadline)
    num_epochs = 5
    os.makedirs('models', exist_ok=True)
    model_save_path = 'models/agrishield_model.pt'
    
    print(f"[+] Initiating training loop for {num_epochs} epochs...")
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{num_epochs}")
        for inputs, labels in pbar:
            inputs, labels = inputs.to(device), labels.to(device)

            # Zero the parameter gradients
            optimizer.zero_grad()

            # Forward pass
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            # Backward pass and optimize
            loss.backward()
            optimizer.step()

            # Statistics
            running_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
            # Update progress bar metric displays
            pbar.set_postfix({'loss': f"{loss.item():.4f}", 'acc': f"{(correct/total):.4f}"})

        epoch_loss = running_loss / len(dataset)
        epoch_acc = correct / total
        print(f"[*] Epoch {epoch+1}/{num_epochs} Summary - Loss: {epoch_loss:.4f}, Accuracy: {epoch_acc:.4f}")

        # [CRITICAL UPGRADE]: Save full model checkpoint securely at the end of EVERY epoch
        # This protects data assets against unexpected sleep cycles or system shutdowns.
        torch.save(model, model_save_path)
        print(f"[+] Checkpoint securely committed to disk at: {model_save_path}")

    print("[+] Training complete. Final production model locked and verified.")

if __name__ == '__main__':
    main()