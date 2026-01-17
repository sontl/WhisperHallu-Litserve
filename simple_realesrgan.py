"""
Simple Real-ESRGAN implementation using PyTorch directly
"""
import torch
import torch.nn as nn
import numpy as np
from PIL import Image
import requests
import os
import logging
from typing import Optional

logger = logging.getLogger("simple_realesrgan")

# Model URLs from official Real-ESRGAN releases
MODEL_URLS = {
    'RealESRGAN_x4plus': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
    'RealESRGAN_x2plus': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth',
    'RealESRGAN_x4plus_anime_6B': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth',
}

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

class RRDBBlock(nn.Module):
    """Residual in Residual Dense Block"""
    def __init__(self, num_feat=64, num_grow_ch=32):
        super(RRDBBlock, self).__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x):
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x

class ResidualDenseBlock(nn.Module):
    """Residual Dense Block"""
    def __init__(self, num_feat=64, num_grow_ch=32):
        super(ResidualDenseBlock, self).__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x

class RRDBNet(nn.Module):
    """Real-ESRGAN network with optional pixel unshuffle for x2 models"""
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4):
        super(RRDBNet, self).__init__()
        self.scale = scale
        
        # For x2 model, use pixel unshuffle to reduce spatial size and increase channels
        # x2plus model uses scale=2 internally but pixel_unshuffle with factor 2 first
        if scale == 2:
            num_in_ch = num_in_ch * 4  # 3 * 4 = 12 channels after pixel unshuffle
        
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body = nn.Sequential(*[RRDBBlock(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        
        # Upsampling layers
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        # Apply pixel unshuffle for x2 model
        if self.scale == 2:
            x = self._pixel_unshuffle(x, 2)
        
        feat = self.conv_first(x)
        body_feat = self.conv_body(self.body(feat))
        feat = feat + body_feat
        
        # Upsample - x4 model does 2x twice, x2 model does 2x twice (to compensate for pixel unshuffle)
        feat = self.lrelu(self.conv_up1(torch.nn.functional.interpolate(feat, scale_factor=2, mode='nearest')))
        feat = self.lrelu(self.conv_up2(torch.nn.functional.interpolate(feat, scale_factor=2, mode='nearest')))
        out = self.conv_last(self.lrelu(self.conv_hr(feat)))
        
        return out
    
    def _pixel_unshuffle(self, x, scale):
        """Reverse of pixel shuffle - reduces spatial size, increases channels"""
        b, c, h, w = x.shape
        out_c = c * (scale ** 2)
        out_h = h // scale
        out_w = w // scale
        
        x = x.view(b, c, out_h, scale, out_w, scale)
        x = x.permute(0, 1, 3, 5, 2, 4).contiguous()
        x = x.view(b, out_c, out_h, out_w)
        return x

class SimpleRealESRGAN:
    """Simple Real-ESRGAN implementation"""
    
    def __init__(self, device='auto', scale=4, model_name='RealESRGAN_x4plus'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu') if device == 'auto' else torch.device(device)
        self.scale = scale
        self.model_name = model_name
        self.model = None
        self.model_path = None
        self.using_real_model = False
        
    def _download_model(self, model_name: str) -> Optional[str]:
        """Download Real-ESRGAN model weights"""
        if model_name not in MODEL_URLS:
            logger.warning(f"Unknown model: {model_name}, available: {list(MODEL_URLS.keys())}")
            return None
            
        os.makedirs(MODEL_DIR, exist_ok=True)
        model_path = os.path.join(MODEL_DIR, f"{model_name}.pth")
        
        if os.path.exists(model_path):
            logger.info(f"Model already exists: {model_path}")
            return model_path
            
        url = MODEL_URLS[model_name]
        logger.info(f"Downloading {model_name} from {url}...")
        
        try:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) < 8192:  # Log every ~1MB
                                logger.info(f"Download progress: {pct:.1f}%")
            
            logger.info(f"Model downloaded successfully: {model_path}")
            return model_path
            
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            if os.path.exists(model_path):
                os.remove(model_path)
            return None
        
    def load_model(self, model_path: Optional[str] = None):
        """Load Real-ESRGAN model"""
        # Try to download official weights if no path provided
        if model_path is None:
            # Map scale to appropriate model
            if self.scale == 2:
                model_name = 'RealESRGAN_x2plus'
            else:
                model_name = self.model_name if self.model_name in MODEL_URLS else 'RealESRGAN_x4plus'
            
            model_path = self._download_model(model_name)
        
        if model_path and os.path.exists(model_path):
            try:
                logger.info(f"Loading Real-ESRGAN model from {model_path}")
                
                # Determine model architecture based on filename
                if 'x2plus' in model_path.lower():
                    num_block = 23
                    scale = 2
                elif 'anime_6B' in model_path.lower():
                    num_block = 6
                    scale = 4
                else:
                    num_block = 23
                    scale = 4
                
                self.model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, 
                                     num_block=num_block, num_grow_ch=32, scale=scale)
                
                # Load state dict
                loadnet = torch.load(model_path, map_location=self.device)
                
                # Handle different checkpoint formats
                if 'params_ema' in loadnet:
                    keyname = 'params_ema'
                elif 'params' in loadnet:
                    keyname = 'params'
                else:
                    keyname = None
                
                if keyname:
                    self.model.load_state_dict(loadnet[keyname], strict=True)
                else:
                    self.model.load_state_dict(loadnet, strict=True)
                
                self.model.to(self.device)
                self.model.eval()
                self.using_real_model = True
                self.scale = scale  # Update scale based on loaded model
                logger.info(f"Real-ESRGAN model loaded successfully (scale={scale}, blocks={num_block})")
                return
                
            except Exception as e:
                logger.warning(f"Failed to load Real-ESRGAN weights: {e}, using fallback")
        
        # Fallback to simple bicubic model
        logger.warning("Using bicubic fallback (no Real-ESRGAN weights)")
        self.model = self._create_simple_model()
        self.model.to(self.device)
        self.model.eval()
        self.using_real_model = False
        
    def _create_simple_model(self):
        """Create a simple upsampling model as fallback - uses bicubic interpolation only"""
        class SimpleUpsampler(nn.Module):
            def __init__(self, scale=4):
                super().__init__()
                self.scale = scale
                
            def forward(self, x):
                # Pure bicubic upsampling - no random convolutions that corrupt the image
                x = torch.nn.functional.interpolate(x, scale_factor=self.scale, mode='bicubic', align_corners=False)
                return torch.clamp(x, 0, 1)
        
        return SimpleUpsampler(self.scale)
    
    def enhance(self, img_array, outscale=None):
        """Enhance image using the model"""
        if self.model is None:
            self.load_model()
            
        if outscale is None:
            outscale = self.scale
            
        # Convert numpy array to tensor
        if isinstance(img_array, np.ndarray):
            # Make a copy to ensure positive strides
            img_array = np.ascontiguousarray(img_array)
            
            # Convert BGR to RGB if needed
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                img_array = img_array[:, :, ::-1].copy()  # BGR to RGB with copy
            
            # Normalize to [0, 1]
            img_tensor = torch.from_numpy(img_array.copy()).float() / 255.0
            img_tensor = img_tensor.permute(2, 0, 1).unsqueeze(0)  # HWC to NCHW
        else:
            img_tensor = img_array
            
        img_tensor = img_tensor.to(self.device)
        
        with torch.no_grad():
            output = self.model(img_tensor)
            
        # Convert back to numpy
        output = output.squeeze(0).permute(1, 2, 0).cpu().numpy()
        output = np.clip(output * 255.0, 0, 255).astype(np.uint8)
        
        # Make contiguous and convert RGB back to BGR for OpenCV compatibility
        output = np.ascontiguousarray(output[:, :, ::-1])
        
        return output, None  # Return tuple to match Real-ESRGAN interface

def create_simple_realesrgan(device='auto', scale=4, model_name='RealESRGAN_x4plus'):
    """Factory function to create SimpleRealESRGAN instance"""
    return SimpleRealESRGAN(device=device, scale=scale, model_name=model_name)