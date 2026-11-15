import { useEffect, useRef } from "react";

const samples = {
  actual: [640, 696, 680, 565, 550, 455, 440, 338, 427, 570, 705, 695, 650],
  baseline: [875, 945, 928, 770, 750, 624, 600, 481, 592, 795, 960, 950, 882],
};

export default function PowerChart({ factor = 1 }: { factor?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    function draw() {
      if (!canvas?.isConnected) return;
      const { clientWidth: width, clientHeight: height } = canvas;
      if (!width || !height) return;
      const rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize);
      const density = Math.min(window.devicePixelRatio, 2);
      canvas.width = width * density;
      canvas.height = height * density;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.scale(density, density);
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.font = `400 ${rootSize * 0.64}px Inter, sans-serif`;
      const left = rootSize * 2.65;
      const right = width - rootSize * 0.5;
      const top = rootSize * 1.65;
      const bottom = height - rootSize * 1.85;
      const max = factor === 1 ? 1200 : factor > 0.28 ? 500 : 300;
      const y = (value: number) => bottom - (value / max) * (bottom - top);
      ctx.fillStyle = "#98aabe";
      ctx.fillText("kW", 0, rootSize * 0.57);
      for (let step = 0; step <= 3; step += 1) {
        const value = Math.round((max * step) / 3);
        const tick = bottom - (step / 3) * (bottom - top);
        ctx.fillText(value.toLocaleString("vi-VN"), 0, tick + 2.5);
        ctx.beginPath();
        ctx.moveTo(left, tick);
        ctx.lineTo(right, tick);
        ctx.strokeStyle = "#22354c";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      const series = [
        { values: samples.baseline, color: "#35d5a5", weight: 2.1 },
        { values: samples.actual, color: "#438cff", weight: 1.5 },
      ];
      for (const { values, color, weight } of series) {
        ctx.beginPath();
        values.forEach((value, index) => {
          const x = left + (index / (values.length - 1)) * (right - left);
          if (index === 0) ctx.moveTo(x, y(value * factor));
          else ctx.lineTo(x, y(value * factor));
        });
        ctx.strokeStyle = color;
        ctx.lineWidth = weight;
        ctx.stroke();
      }
      ["18:00", "21:00", "00:00", "03:00", "06:00"].forEach((label, index, all) => {
        ctx.textAlign = index === 0 ? "left" : index === all.length - 1 ? "right" : "center";
        ctx.fillText(label, left + (index / 4) * (right - left), height - rootSize * 0.4);
      });
    }
    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    void document.fonts.ready.then(draw);
    return () => observer.disconnect();
  }, [factor]);

  return <canvas className="power-chart" ref={ref} role="img" aria-label="Biểu đồ công suất, đường xanh dương thực tế nằm dưới đường cơ sở màu xanh lá trong ca vận hành" />;
}
