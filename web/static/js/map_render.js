class MapRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.width = 400; // From config
        this.height = 400;
        this.canvas.width = this.width;
        this.canvas.height = this.height;
    }

    render(binaryData) {
        const imageData = this.ctx.createImageData(this.width, this.height);
        const data = new Uint8Array(binaryData);
        
        for (let i = 0; i < data.length; i++) {
            const val = data[i];
            const idx = i * 4;
            
            // 0=unknown, 127=free, 255=occupied (typical mapping values)
            if (val === 0) { // Unknown -> Light Grey
                imageData.data[idx] = 180;
                imageData.data[idx+1] = 180;
                imageData.data[idx+2] = 180;
            } else if (val === 255) { // Occupied -> Black
                imageData.data[idx] = 0;
                imageData.data[idx+1] = 0;
                imageData.data[idx+2] = 0;
            } else { // Free -> White
                imageData.data[idx] = 255;
                imageData.data[idx+1] = 255;
                imageData.data[idx+2] = 255;
            }
            imageData.data[idx+3] = 255; // Alpha
        }
        
        this.ctx.putImageData(imageData, 0, 0);
    }
}
