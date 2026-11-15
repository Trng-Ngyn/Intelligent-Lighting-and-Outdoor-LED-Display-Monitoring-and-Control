import { useEffect, useRef } from "react";

function drawMap(ctx: CanvasRenderingContext2D, width: number, height: number, showNetwork: boolean) {
  const fontSize = Math.min(15, Math.max(10, width / 57));
  ctx.save();
  ctx.scale(width / 1000, height / 600);
  ctx.fillStyle = "#0b1927";
  ctx.fillRect(0, 0, 1000, 600);

  for (let row = -1; row < 9; row += 1) {
    for (let col = -1; col < 13; col += 1) {
      const x = col * 87 - (row % 2) * 16 - 17;
      const y = row * 76 + 60;
      ctx.fillStyle = (col + 3 * row) % 6 === 0 ? "#102c31" : "#122436";
      ctx.beginPath();
      if (typeof ctx.roundRect === "function") ctx.roundRect(x, y, 66, 51, 3.5);
      else ctx.rect(x, y, 66, 51);
      ctx.fill();
    }
  }

  function river() {
    ctx.beginPath();
    ctx.moveTo(649, -25);
    ctx.bezierCurveTo(545, 59, 665, 151, 680, 236);
    ctx.bezierCurveTo(704, 308, 595, 333, 596, 413);
    ctx.bezierCurveTo(585, 483, 686, 579, 787, 630);
  }

  river();
  ctx.strokeStyle = "#123a50";
  ctx.lineWidth = 71;
  ctx.stroke();
  river();
  ctx.strokeStyle = "#17445b";
  ctx.lineWidth = 53;
  ctx.stroke();

  function road(x1: number, y1: number, x2: number, y2: number, color: string, weight: number) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = color;
    ctx.lineWidth = weight;
    ctx.stroke();
  }

  for (let row = 0; row < 10; row += 1) {
    road(-15, 13 + row * 84, 1020, 69 + row * 84, "#294155", 7);
  }

  for (let col = -3; col < 11; col += 1) {
    road(col * 112 + 82, -16, col * 112 + 279, 635, "#294155", 7.5);
  }

  road(-28, 463, 1030, 140, "#54647a", 12);
  road(-28, 463, 1030, 140, "#25384e", 9);
  road(165, -30, 475, 630, "#54647a", 12);
  road(165, -30, 475, 630, "#25384e", 9);

  if (showNetwork) {
    for (let row = 0; row < 9; row += 1) {
      for (let col = 0; col < 14; col += 1) {
        if ((row * 13 + col * 3) % 11 === 0) continue;
        const x = 44 + col * 72 + Math.sin(row * 2 + col * 0.5) * 12;
        const y = 47 + row * 56 + Math.cos(col * 0.34 + row * 0.6) * 8;
        const color = col === 0 ? "#efb648" : (row * 14 + col) % 31 === 12 ? "#f26776" : "#33d4a4";
        ctx.beginPath();
        ctx.arc(x, y, 7.2, 0, Math.PI * 2);
        ctx.fillStyle = `${color}24`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x, y, 2.85, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      }
    }
  }

  ctx.restore();
  const labels: [string, number, number, boolean][] = [
    ["THANH KHÊ", 0.05, 0.15, true], ["HẢI CHÂU", 0.215, 0.35, true],
    ["SƠN TRÀ", 0.78, 0.40, true], ["NGŨ HÀNH SƠN", 0.755, 0.845, true],
    ["Bạch Đằng", 0.405, 0.19, false], ["Nguyễn Văn Linh", 0.295, 0.60, false],
    ["SÔNG HÀN", 0.647, 0.575, false],
  ];
  for (const [label, x, y, primary] of labels) {
    ctx.font = `${primary ? 650 : 450} ${primary ? fontSize : fontSize * 0.63}px Inter, sans-serif`;
    ctx.fillStyle = primary ? "#7591a7" : "#8aa5bb";
    ctx.fillText(label, x * width, y * height);
  }
}

export default function MapBackdrop({ showNetwork = true }: { showNetwork?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    function paint() {
      if (!canvas?.isConnected) return;
      const { clientWidth: width, clientHeight: height } = canvas;
      if (!width || !height) return;
      const density = Math.min(window.devicePixelRatio, 2);
      canvas.width = width * density;
      canvas.height = height * density;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.scale(density, density);
      drawMap(ctx, width, height, showNetwork);
    }
    const observer = new ResizeObserver(paint);
    observer.observe(canvas);
    void document.fonts.ready.then(paint);
    return () => observer.disconnect();
  }, [showNetwork]);

  return <canvas className="map-backdrop" ref={ref} aria-hidden="true" />;
}
