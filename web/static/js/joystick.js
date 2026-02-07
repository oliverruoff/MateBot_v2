class Joystick {
    constructor(elementId, onMove) {
        this.element = document.getElementById(elementId);
        this.onMove = onMove;
        this.active = false;
        this.centerX = 0;
        this.centerY = 0;
        
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
        
        // Normalize to -1.0 to 1.0
        // vy is -dy because up is positive Y in robot frame
        const vx = -dy / maxDist * 0.5; // Max 0.5 m/s
        const vy = dx / maxDist * 0.5;
        
        this.onMove(vx, vy, 0);
    }

    stop() {
        if (!this.active) return;
        this.active = false;
        this.onMove(0, 0, 0);
    }
}
