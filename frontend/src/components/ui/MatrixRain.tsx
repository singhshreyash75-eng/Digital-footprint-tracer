import { useEffect, useRef } from "react";

type MatrixRainProps = {
  active?: boolean;
};

const GLYPHS =
  "01ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%&*@+-<>[]{}()/\\|";

type Stream = {
  x: number;
  y: number;
  speed: number;
  length: number;
  opacity: number;
  fontSize: number;
  tick: number;
};

export default function MatrixRain({
  active = true,
}: MatrixRainProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!active) {
      return;
    }

    const canvas = canvasRef.current;

    if (!canvas) {
      return;
    }

    const context = canvas.getContext("2d");

    if (!context) {
      return;
    }

    let animationFrame = 0;
    let width = 0;
    let height = 0;
    let streams: Stream[] = [];

    const getRandomGlyph = () =>
      GLYPHS[Math.floor(Math.random() * GLYPHS.length)];

    const createStream = (x: number): Stream => ({
      x,
      y: -Math.random() * height,
      speed: 0.48 + Math.random() * 0.95,
      length: 16 + Math.floor(Math.random() * 30),
      opacity: 0.18 + Math.random() * 0.32,
      fontSize: 10 + Math.random() * 3,
      tick: Math.random() * 100,
    });

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      width = window.innerWidth;
      height = window.innerHeight;

      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      context.setTransform(dpr, 0, 0, dpr, 0, 0);

      /* Dense coverage without making the foreground unreadable. */
      const streamCount = Math.floor(width / 7);

      streams = Array.from(
        { length: streamCount },
        (_, index) => createStream(index * 7 + Math.random() * 6),
      );

      context.clearRect(0, 0, width, height);
    };

    const draw = () => {
      /* Low fade = longer, slower-looking trails. */
      context.fillStyle = "rgba(1, 9, 6, 0.10)";
      context.fillRect(0, 0, width, height);

      streams.forEach((stream) => {
        stream.tick += 1;

        const lineHeight = stream.fontSize * 1.5;

        for (let i = 0; i < stream.length; i += 1) {
          const y = stream.y - i * lineHeight;

          if (y < -lineHeight || y > height + lineHeight) {
            continue;
          }

          const fade = 1 - i / stream.length;
          const isLead =
            i === 0 || (stream.tick % 13 === 0 && i === 1);

          context.font = `${stream.fontSize}px monospace`;

          if (isLead) {
            context.fillStyle = "rgba(190, 255, 215, 0.9)";
          } else {
            const alpha = Math.max(
              0.022,
              stream.opacity * fade,
            );

            context.fillStyle = `rgba(41, 255, 130, ${alpha})`;
          }

          const jitter = Math.random() > 0.97
            ? (Math.random() - 0.5) * 2
            : 0;

          context.fillText(
            getRandomGlyph(),
            stream.x + jitter,
            y,
          );
        }

        /* Deliberately slower than the previous pass. */
        stream.y += stream.speed * stream.fontSize * 0.58;

        if (stream.y - stream.length * lineHeight > height) {
          stream.y = -Math.random() * height * 0.55;
          stream.speed = 0.48 + Math.random() * 0.95;
          stream.length = 16 + Math.floor(Math.random() * 30);
          stream.opacity = 0.18 + Math.random() * 0.32;
          stream.fontSize = 10 + Math.random() * 3;
          stream.tick = Math.random() * 100;
        }
      });

      animationFrame = window.requestAnimationFrame(draw);
    };

    resize();
    draw();

    window.addEventListener("resize", resize);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", resize);
    };
  }, [active]);

  return (
    <canvas
      ref={canvasRef}
      className={`matrix-rain ${active ? "matrix-rain--active" : ""}`}
      aria-hidden="true"
    />
  );
}
