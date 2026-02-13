class Joystick {
    constructor(elementId, onMove) {
        this.element = document.getElementById(elementId);
        this.onMove = onMove;
        this.active = false;
        this.centerX = 0;
        this.centerY = 0;
        
        // Create thumb element
        this.thumb = document.createElement('div');
        this.thumb.style.width = '60px';
        this.thumb.style.height = '60px';
        this.thumb.style.background = '#555';
        this.thumb.style.borderRadius = '50%';
        this.thumb.style.position = 'absolute';
        this.thumb.style.left = '70px'; // (200-60)/2
        this.thumb.style.top = '70px';
        this.thumb.style.border = '2px solid #777';
        this.element.appendChild(this.thumb);
        
        this.element.addEventListener('mousedown', this.start.bind(this));
        window.addEventListener('mousemove', this.move.bind(this));
        window.addEventListener('mouseup', this.stop.bind(this));
        
        this.element.addEventListener('touchstart', this.start.bind(this));
        window.addEventListener('touchmove', this.move.bind(this));
        window.addEventListener('touchend', this.stop.bind(this));
    }

    start(e) {
        this.active = true;
        const rect = this.element.getBoundingClientRect();
        this.centerX = rect.left + rect.width / 2;
        this.centerY = rect.top + rect.height / 2;
    }

    move(e) {
        if (!this.active) return;
        
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        
        let dx = clientX - this.centerX;
        let dy = clientY - this.centerY;
        
        const dist = Math.sqrt(dx*dx + dy*dy);
        const maxDist = 80;
        
        if (dist > maxDist) {
            dx *= maxDist / dist;
            dy *= maxDist / dist;
        }
        
        // Update thumb position
        this.thumb.style.transform = `translate(${dx}px, ${dy}px)`;
        
        // Normalize to -1.0 to 1.0
        const vx = -dy / maxDist * 0.5;
        const vy = dx / maxDist * 0.5;
        
        this.onMove(vx, vy, 0);
    }

    stop() {
        if (!this.active) return;
        this.active = false;
        this.thumb.style.transform = `translate(0px, 0px)`;
        this.onMove(0, 0, 0);
    }
}
