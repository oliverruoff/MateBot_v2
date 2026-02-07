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
            // 0=unknown (grey), 127=free (white?), 255=occupied (black)
            // Let's adjust for visibility
            if (val === 127) { // Unknown
                imageData.data[idx] = 50;
                imageData.data[idx+1] = 50;
                imageData.data[idx+2] = 50;
            } else if (val === 255) { // Occupied
                imageData.data[idx] = 255;
                imageData.data[idx+1] = 0;
                imageData.data[idx+2] = 0;
            } else { // Free
                imageData.data[idx] = 200;
                imageData.data[idx+1] = 200;
                imageData.data[idx+2] = 200;
            }
            imageData.data[idx+3] = 255; // Alpha
        }
        
        this.ctx.putImageData(imageData, 0, 0);
    }
}
