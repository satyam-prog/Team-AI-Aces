// EduEagle - Custom High-Performance Canvas Charts (Zero External Dependencies)

const EagleCharts = {
  // 1. 6-Pillar Radar / Spider Chart for 360 Student Dossier
  drawRadarChart(canvasId, values, labels, color = "#2563eb") {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(centerX, centerY) - 38;
    const numPoints = labels.length;
    const angleStep = (Math.PI * 2) / numPoints;

    // Draw background concentric polygons (levels 20%, 40%, 60%, 80%, 100%)
    const levels = 5;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
    ctx.lineWidth = 1;

    for (let l = 1; l <= levels; l++) {
      const levelRadius = (radius / levels) * l;
      ctx.beginPath();
      for (let i = 0; i < numPoints; i++) {
        const angle = i * angleStep - Math.PI / 2;
        const x = centerX + Math.cos(angle) * levelRadius;
        const y = centerY + Math.sin(angle) * levelRadius;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.stroke();
    }

    // Draw radial axis lines from center to outer points
    ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
    for (let i = 0; i < numPoints; i++) {
      const angle = i * angleStep - Math.PI / 2;
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius;
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(x, y);
      ctx.stroke();

      // Draw label
      const labelDistance = radius + 22;
      const lx = centerX + Math.cos(angle) * labelDistance;
      const ly = centerY + Math.sin(angle) * labelDistance;

      ctx.fillStyle = "#94a3b8";
      ctx.font = "11px -apple-system, BlinkMacSystemFont, Segoe UI, Roboto";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      // Split label if multi-word for compact display
      const labelText = labels[i];
      ctx.fillText(labelText, lx, ly);
    }

    // Draw the student's actual performance polygon
    ctx.beginPath();
    for (let i = 0; i < numPoints; i++) {
      const val = Math.max(10, Math.min(100, values[i])) / 100;
      const pointRadius = radius * val;
      const angle = i * angleStep - Math.PI / 2;
      const x = centerX + Math.cos(angle) * pointRadius;
      const y = centerY + Math.sin(angle) * pointRadius;

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();

    // Fill with clean corporate blue
    ctx.fillStyle = "rgba(37, 99, 235, 0.22)";
    ctx.fill();

    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw point markers
    for (let i = 0; i < numPoints; i++) {
      const val = Math.max(10, Math.min(100, values[i])) / 100;
      const pointRadius = radius * val;
      const angle = i * angleStep - Math.PI / 2;
      const x = centerX + Math.cos(angle) * pointRadius;
      const y = centerY + Math.sin(angle) * pointRadius;

      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
      ctx.strokeStyle = "#2563eb";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  },

  // 2. Donut Chart for Cohort Risk Segmentation
  drawDonutChart(canvasId, data, colors) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const centerX = width / 2;
    const centerY = height / 2;
    const outerRadius = Math.min(centerX, centerY) - 15;
    const innerRadius = outerRadius * 0.62;

    const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
    let startAngle = -Math.PI / 2;

    const keys = Object.keys(data);
    keys.forEach((key, index) => {
      const count = data[key];
      const sliceAngle = (count / total) * (Math.PI * 2);
      const endAngle = startAngle + sliceAngle;

      ctx.beginPath();
      ctx.arc(centerX, centerY, outerRadius, startAngle, endAngle);
      ctx.arc(centerX, centerY, innerRadius, endAngle, startAngle, true);
      ctx.closePath();

      ctx.fillStyle = colors[key] || "#64748b";
      ctx.fill();
      ctx.strokeStyle = "#0f172a";
      ctx.lineWidth = 3;
      ctx.stroke();

      startAngle = endAngle;
    });

    // Draw center total count
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 20px -apple-system, BlinkMacSystemFont, Segoe UI";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(`${total}`, centerX, centerY - 6);

    ctx.fillStyle = "#94a3b8";
    ctx.font = "11px -apple-system, BlinkMacSystemFont, Segoe UI";
    ctx.fillText("Students", centerX, centerY + 14);
  },

  // 3. Horizontal Bar Chart for Intervention Efficacy by Type
  drawEfficacyBarChart(containerId, efficacyByType) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = efficacyByType.map(item => {
      const color = item.rate >= 85 ? '#10b981' : (item.rate >= 70 ? '#38bdf8' : '#f59e0b');
      return `
        <div style="margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 4px;">
            <span style="color: #cbd5e1; font-weight: 500;">${item.type}</span>
            <strong style="color: ${color};">${item.rate}% Success (${item.resolved}/${item.total})</strong>
          </div>
          <div style="height: 8px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: hidden;">
            <div style="height: 100%; width: ${item.rate}%; background: ${color}; border-radius: 4px; transition: width 0.6s ease;"></div>
          </div>
        </div>
      `;
    }).join("");
  }
};

window.EagleCharts = EagleCharts;

