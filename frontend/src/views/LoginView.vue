<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import logoImg from '@/resources/logo2.jpg'
import { APP_VERSION } from '@/config/app'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const loginPageRef = ref<HTMLElement | null>(null)
const DISC_COUNT = 9
type TrailPoint = { x: number; y: number; life: number }
type Disc = {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  spin: number
  spinV: number
  mass: number
  heading: number
  curvePhase: number
  curveAmp: number
  turnBias: number
  magnusFactor: number
  trail: TrailPoint[]
}
type Spark = { x: number; y: number; vx: number; vy: number; life: number; size: number }

const discs = ref<Disc[]>([])
const sparks = ref<Spark[]>([])
const pointer = ref({ x: 0, y: 0, vx: 0, vy: 0, active: false, lastTs: 0, lastX: 0, lastY: 0 })
const scene = ref({ w: 0, h: 0 })
let rafId: number | null = null

function rand(min: number, max: number) {
  return min + Math.random() * (max - min)
}

function syncSceneSize() {
  const el = loginPageRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  scene.value.w = rect.width
  scene.value.h = rect.height
  for (const d of discs.value) {
    d.x = Math.max(d.r, Math.min(scene.value.w - d.r, d.x))
    d.y = Math.max(d.r, Math.min(scene.value.h - d.r, d.y))
  }
}

function initDiscs() {
  const next: Disc[] = []
  const { w, h } = scene.value
  for (let i = 0; i < DISC_COUNT; i += 1) {
    const r = rand(12, 18)
    next.push({
      x: rand(r + 6, Math.max(r + 6, w - r - 6)),
      y: rand(r + 6, Math.max(r + 6, h - r - 6)),
      vx: rand(-0.52, 0.52),
      vy: rand(-0.52, 0.52),
      r,
      spin: rand(0, 360),
      spinV: rand(-3.2, 3.2),
      mass: r * r,
      heading: rand(0, 360),
      curvePhase: rand(0, Math.PI * 2),
      curveAmp: rand(0.008, 0.016),
      turnBias: Math.random() > 0.5 ? 1 : -1,
      magnusFactor: rand(0.00125, 0.0021),
      trail: [],
    })
  }
  discs.value = next
}

function emitSparks(x: number, y: number, amount: number, baseSpeed = 1.4) {
  const n = Math.max(1, amount)
  for (let i = 0; i < n; i += 1) {
    const angle = rand(0, Math.PI * 2)
    const speed = rand(baseSpeed * 0.5, baseSpeed * 1.1)
    sparks.value.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: rand(0.5, 0.85),
      size: rand(1.2, 2.6),
    })
  }
}

function onPointerMove(event: PointerEvent) {
  const el = loginPageRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const now = performance.now()
  const dt = Math.max(1, now - (pointer.value.lastTs || now))
  const vx = ((x - pointer.value.lastX) / dt) * 16.67
  const vy = ((y - pointer.value.lastY) / dt) * 16.67
  pointer.value = { x, y, vx, vy, active: true, lastTs: now, lastX: x, lastY: y }
}

function onPointerLeave() {
  pointer.value.active = false
}

function resolveDiscCollision(a: Disc, b: Disc): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const dist = Math.hypot(dx, dy) || 0.001
  const minDist = a.r + b.r
  if (dist >= minDist) return 0

  const nx = dx / dist
  const ny = dy / dist
  const overlap = minDist - dist
  a.x -= nx * overlap * 0.5
  a.y -= ny * overlap * 0.5
  b.x += nx * overlap * 0.5
  b.y += ny * overlap * 0.5

  const rvx = b.vx - a.vx
  const rvy = b.vy - a.vy
  const relVel = rvx * nx + rvy * ny
  if (relVel > 0) return 0

  const restitution = 0.9
  const impulse = (-(1 + restitution) * relVel) / (1 / a.mass + 1 / b.mass)
  const ix = impulse * nx
  const iy = impulse * ny
  a.vx -= ix / a.mass
  a.vy -= iy / a.mass
  b.vx += ix / b.mass
  b.vy += iy / b.mass

  const tangentSpin = (rvx * -ny + rvy * nx) * 0.08
  a.spinV -= tangentSpin / Math.max(1, a.r)
  b.spinV += tangentSpin / Math.max(1, b.r)
  a.spinV = Math.max(-5.2, Math.min(5.2, a.spinV))
  b.spinV = Math.max(-5.2, Math.min(5.2, b.spinV))
  return Math.abs(relVel)
}

function shortestAngleDelta(target: number, current: number) {
  return ((target - current + 540) % 360) - 180
}

function updateDiscs(frameTs: number) {
  const { w, h } = scene.value
  if (!w || !h) return

  const influenceRadius = 90
  for (const d of discs.value) {
    if (pointer.value.active) {
      const dx = d.x - pointer.value.x
      const dy = d.y - pointer.value.y
      const dist = Math.hypot(dx, dy) || 0.001
      if (dist < influenceRadius) {
        const force = (influenceRadius - dist) / influenceRadius
        const nx = dx / dist
        const ny = dy / dist
        d.vx += nx * force * 1.1 + pointer.value.vx * force * 0.07
        d.vy += ny * force * 1.1 + pointer.value.vy * force * 0.07
      }
    }

    d.vx *= 0.983
    d.vy *= 0.983
    d.spinV *= 0.996

    const speed = Math.hypot(d.vx, d.vy)
    if (speed > 0.05) {
      const nx = -d.vy / speed
      const ny = d.vx / speed
      const baselineCurve = d.turnBias * (0.0008 + speed * 0.00065)
      const waveCurve = Math.sin(frameTs * 0.0017 + d.curvePhase) * d.curveAmp
      const spinCurve = d.spinV * 0.00055
      const curve = baselineCurve + waveCurve + spinCurve
      d.vx += nx * curve
      d.vy += ny * curve

      // Magnus effect: spin induces side-force, creating frisbee-like curved flight.
      const magnus = d.spinV * speed * d.magnusFactor
      d.vx += nx * magnus
      d.vy += ny * magnus

      const targetHeading = (Math.atan2(d.vy, d.vx) * 180) / Math.PI
      d.heading += shortestAngleDelta(targetHeading, d.heading) * 0.075
    }

    d.x += d.vx
    d.y += d.vy
    d.spin += d.spinV * 1.22

    for (const p of d.trail) p.life -= 0.06
    d.trail = d.trail.filter((p) => p.life > 0)
    const last = d.trail[d.trail.length - 1]
    if (!last || Math.hypot(d.x - last.x, d.y - last.y) > 4) {
      d.trail.push({ x: d.x, y: d.y, life: 1 })
      if (d.trail.length > 18) d.trail.shift()
    }

    const bounce = 0.8
    if (d.x - d.r <= 0) {
      d.x = d.r
      const impact = Math.abs(d.vx)
      d.vx = Math.abs(d.vx) * bounce
      if (impact > 0.8) emitSparks(d.x + d.r * 0.1, d.y, 2, 1.2)
    } else if (d.x + d.r >= w) {
      d.x = w - d.r
      const impact = Math.abs(d.vx)
      d.vx = -Math.abs(d.vx) * bounce
      if (impact > 0.8) emitSparks(d.x - d.r * 0.1, d.y, 2, 1.2)
    }

    if (d.y - d.r <= 0) {
      d.y = d.r
      const impact = Math.abs(d.vy)
      d.vy = Math.abs(d.vy) * bounce
      if (impact > 0.8) emitSparks(d.x, d.y + d.r * 0.1, 2, 1.2)
    } else if (d.y + d.r >= h) {
      d.y = h - d.r
      const impact = Math.abs(d.vy)
      d.vy = -Math.abs(d.vy) * bounce
      if (impact > 0.8) emitSparks(d.x, d.y - d.r * 0.1, 2, 1.2)
    }
  }

  for (let i = 0; i < discs.value.length; i += 1) {
    for (let j = i + 1; j < discs.value.length; j += 1) {
      const a = discs.value[i]!
      const b = discs.value[j]!
      const impact = resolveDiscCollision(a, b)
      if (impact > 0.7) {
        emitSparks((a.x + b.x) * 0.5, (a.y + b.y) * 0.5, impact > 1.1 ? 3 : 2, 1.4)
      }
    }
  }

  for (const s of sparks.value) {
    s.x += s.vx
    s.y += s.vy
    s.vx *= 0.95
    s.vy *= 0.95
    s.life -= 0.075
  }
  sparks.value = sparks.value.filter((s) => s.life > 0)
}

function animate(ts: number) {
  updateDiscs(ts)
  rafId = window.requestAnimationFrame(animate)
}

function discStyle(d: { x: number; y: number; r: number; spin: number }) {
  const size = d.r * 2
  return {
    width: `${size}px`,
    height: `${size}px`,
    transform: `translate3d(${(d.x - d.r).toFixed(2)}px, ${(d.y - d.r).toFixed(2)}px, 0)`,
  }
}

function discCoreStyle(d: { spin: number; heading: number; curvePhase: number }) {
  const visualAngle = d.heading + d.spin * 0.34
  const delay = -((d.curvePhase / (Math.PI * 2)) * 3.5).toFixed(2)
  return {
    transform: `rotate(${visualAngle.toFixed(2)}deg)`,
    animationDelay: `${delay}s`,
  }
}

function trailSegmentStyle(a: TrailPoint, b: TrailPoint) {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy)
  const angle = (Math.atan2(dy, dx) * 180) / Math.PI
  const opacity = Math.max(0.03, Math.min(0.5, Math.min(a.life, b.life) * 0.5))
  return {
    left: `${a.x.toFixed(2)}px`,
    top: `${a.y.toFixed(2)}px`,
    width: `${len.toFixed(2)}px`,
    opacity: opacity.toFixed(3),
    transform: `translateY(-50%) rotate(${angle.toFixed(2)}deg)`,
  }
}

function trailSegmentStyleAt(disc: Disc, index: number, point: TrailPoint) {
  const prev = disc.trail[index] ?? point
  return trailSegmentStyle(prev, point)
}

function sparkStyle(s: Spark) {
  return {
    left: `${s.x.toFixed(2)}px`,
    top: `${s.y.toFixed(2)}px`,
    width: `${s.size.toFixed(2)}px`,
    height: `${s.size.toFixed(2)}px`,
    opacity: Math.max(0, Math.min(1, s.life)).toFixed(3),
  }
}

onMounted(() => {
  syncSceneSize()
  initDiscs()
  const target = loginPageRef.value
  if (target) {
    target.addEventListener('pointermove', onPointerMove)
    target.addEventListener('pointerleave', onPointerLeave)
  }
  window.addEventListener('resize', syncSceneSize)
  rafId = window.requestAnimationFrame(animate)
})

onBeforeUnmount(() => {
  const target = loginPageRef.value
  if (target) {
    target.removeEventListener('pointermove', onPointerMove)
    target.removeEventListener('pointerleave', onPointerLeave)
  }
  window.removeEventListener('resize', syncSceneSize)
  if (rafId != null) {
    window.cancelAnimationFrame(rafId)
    rafId = null
  }
})

async function handleLogin() {
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    showToast('登录成功')
    // 没有队伍时跳转到队伍设置页
    if (!auth.hasTeam) {
      router.push('/setup-team')
    } else {
      router.push('/home')
    }
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '登录失败，请检查账号和密码')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div ref="loginPageRef" class="login-page">
    <div class="bg-grid" />
    <div class="bg-sweep" />

    <div class="bg-orb bg-orb--left" />
    <div class="bg-orb bg-orb--right" />

    <div class="particles-layer" aria-hidden="true">
      <template v-for="(disc, i) in discs" :key="`trail-${i}`">
        <span
          v-for="(pt, j) in disc.trail.slice(1)"
          :key="`trail-${i}-${j}`"
          class="trail-segment"
          :style="trailSegmentStyleAt(disc, j, pt)"
        />
      </template>

      <span
        v-for="(disc, i) in discs"
        :key="`disc-${i}`"
        class="particle"
        :style="discStyle(disc)"
      >
        <span class="particle-core" :style="discCoreStyle(disc)" />
      </span>

      <span
        v-for="(spark, i) in sparks"
        :key="`spark-${i}`"
        class="spark"
        :style="sparkStyle(spark)"
      />
    </div>

    <div class="login-card">
      <div class="card-frost card-frost--shine" />
      <div class="card-frost card-frost--edge" />

      <div class="logo-area">
        <div class="logo-ring">
          <div class="logo-ring-arc" />
          <div class="logo-glass" />
          <img :src="logoImg" class="logo-img" alt="Solarc Ultimate" />
        </div>
        <h1>
          SolArc-Ultimate
          <span class="version-tag">{{ APP_VERSION }}</span>
        </h1>
        <p class="system-subtitle">飞盘队伍管理&战力评分系统</p>
      </div>

      <van-form @submit="handleLogin">
        <div class="input-glass-wrap">
          <van-cell-group inset class="input-glass">
            <van-field
              v-model="username"
              name="username"
              left-icon="user-o"
              placeholder="用户名 / 邮箱"
              autocomplete="username"
              :rules="[{ required: true, message: '请输入用户名或邮箱' }]"
            />
            <van-field
              v-model="password"
              type="password"
              name="password"
              left-icon="lock"
              placeholder="登录密码"
              autocomplete="current-password"
              :rules="[{ required: true, message: '请输入密码' }]"
            />
          </van-cell-group>
        </div>
        <div class="login-action">
          <van-button round block type="primary" native-type="submit" :loading="loading" class="login-btn" color="linear-gradient(135deg, #0ea5e9 0%, #1d4ed8 100%)">
            <span class="btn-label">登&nbsp;&nbsp;录</span>
          </van-button>
        </div>
        <div class="forgot-row">
          <button class="txt-link" type="button" @click="$router.push('/forgot-password')">
            忘记密码 &rsaquo;
          </button>
        </div>
      </van-form>

      <div class="seg-divider" />

      <div class="action-links">
        <van-button plain block class="cyber-btn" @click="$router.push('/register')">
          注册 · 申请加入队伍
        </van-button>
      </div>

      <div class="rankings-entry">
        <van-button
          plain
          block
          size="small"
          class="rankings-entry-btn"
          @click="$router.push('/public/rankings')"
        >
          ◈ 联盟排行榜 · 无需登录
        </van-button>
      </div>

      <div class="login-copyright">
        <div>© <span class="copyright-arc">ARC</span> · All Rights Reserved.</div>
        <a
          class="icp-link"
          href="https://beian.miit.gov.cn/"
          target="_blank"
          rel="noopener noreferrer"
        >
          沪ICP备2026021594号-2
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100dvh;
  padding: 30px 16px 20px;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(1200px 700px at 8% 12%, rgba(14, 165, 233, 0.24), transparent 58%),
    radial-gradient(900px 600px at 90% 82%, rgba(37, 99, 235, 0.2), transparent 62%),
    linear-gradient(135deg, #060c16 0%, #071425 38%, #040b18 100%);
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 38px 38px;
  mask-image: radial-gradient(circle at 50% 45%, #000 38%, transparent 82%);
  opacity: 0.55;
  z-index: 0;
}

.bg-sweep {
  position: absolute;
  inset: -20%;
  background: linear-gradient(110deg, transparent 36%, rgba(125, 211, 252, 0.08) 50%, transparent 64%);
  transform: translateX(-45%) rotate(-6deg);
  animation: sweep 11s ease-in-out infinite;
  z-index: 0;
}

.login-card {
  width: min(430px, 100%);
  padding: 24px 16px 18px;
  border: 1px solid rgba(186, 230, 253, 0.24);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(186, 230, 253, 0.14), rgba(125, 211, 252, 0.08));
  backdrop-filter: blur(14px) saturate(135%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.34),
    inset 0 -18px 28px rgba(15, 23, 42, 0.22),
    0 26px 50px rgba(8, 18, 36, 0.48);
  z-index: 2;
  position: relative;
  overflow: hidden;
  animation: cardEnter 620ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.card-frost {
  position: absolute;
  pointer-events: none;
}

.card-frost--shine {
  left: -28%;
  top: -38%;
  width: 72%;
  height: 220%;
  z-index: 0;
  background: linear-gradient(108deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0));
  transform: rotate(8deg);
  animation: cardSheen 13.8s ease-in-out infinite;
}

.card-frost--edge {
  inset: 0;
  z-index: 0;
  border-radius: inherit;
  box-shadow: 0 0 0 1px rgba(186, 230, 253, 0.22) inset;
}

.logo-area {
  text-align: center;
  margin-bottom: 20px;
  position: relative;
  z-index: 1;
}

.logo-ring {
  width: 96px;
  height: 96px;
  margin: 0 auto 12px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  border: 1px solid rgba(186, 230, 253, 0.3);
  background: linear-gradient(180deg, rgba(191, 219, 254, 0.22), rgba(147, 197, 253, 0.09));
  backdrop-filter: blur(8px) saturate(125%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.44),
    inset 0 -8px 16px rgba(30, 64, 175, 0.2),
    0 10px 28px rgba(14, 165, 233, 0.22);
  animation: pulseRing 4.5s ease-in-out infinite;
}

.logo-ring-arc {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: conic-gradient(
    transparent 0%,
    rgba(14, 165, 233, 0.0) 20%,
    rgba(125, 211, 252, 0.9) 45%,
    rgba(14, 165, 233, 0.95) 55%,
    rgba(125, 211, 252, 0.0) 80%,
    transparent 100%
  );
  mask: radial-gradient(circle, transparent 0, transparent 84%, #000 86%, #000 100%);
  -webkit-mask: radial-gradient(circle, transparent 0, transparent 84%, #000 86%, #000 100%);
  animation: spinArc 5s linear infinite;
  z-index: 0;
  pointer-events: none;
}

.logo-glass {
  position: absolute;
  top: 7px;
  left: 10px;
  width: 40px;
  height: 26px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.42), rgba(255, 255, 255, 0));
  filter: blur(1px);
  pointer-events: none;
}

.logo-img {
  width: 72px;
  height: 72px;
  object-fit: contain;
  border-radius: 14px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.25);
  position: relative;
  z-index: 1;
}

.logo-area h1 {
  margin: 0;
  font-family: 'Orbitron', 'Segoe UI', sans-serif;
  font-size: 26px;
  font-weight: 900;
  letter-spacing: 2px;
  color: #e0f2fe;
  text-shadow:
    0 0 18px rgba(14, 165, 233, 0.55),
    0 4px 16px rgba(14, 165, 233, 0.3);
  animation: titleReveal 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) 200ms both;
}

.version-tag {
  margin-left: 6px;
  font-family: 'Orbitron', monospace;
  font-size: 9px;
  font-weight: 700;
  color: rgba(125, 211, 252, 0.9);
  letter-spacing: 1px;
  display: inline-block;
  padding: 2px 7px;
  border: 1px solid rgba(125, 211, 252, 0.45);
  border-radius: 4px;
  background: rgba(14, 165, 233, 0.12);
  vertical-align: middle;
  animation: versionGlow 2.4s ease-in-out 1.2s infinite;
}

.logo-area p.system-subtitle {
  color: rgba(186, 230, 253, 0.0);
  margin: 8px 0 0;
  font-size: 11px;
  font-family: 'Orbitron', monospace;
  font-weight: 700;
  letter-spacing: 1.5px;
  background: linear-gradient(90deg,
    rgba(125, 211, 252, 0.55) 0%,
    rgba(186, 230, 253, 0.95) 50%,
    rgba(125, 211, 252, 0.55) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

:deep(.van-cell-group--inset) {
  margin: 0;
  border-radius: 14px;
}

.input-glass-wrap {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
}

.input-glass {
  position: relative;
  border: 1px solid rgba(186, 230, 253, 0.24);
  background: linear-gradient(180deg, rgba(186, 230, 253, 0.16), rgba(125, 211, 252, 0.09));
  backdrop-filter: blur(12px) saturate(135%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.42),
    inset 0 -16px 28px rgba(30, 41, 59, 0.22),
    0 12px 26px rgba(2, 6, 23, 0.32);
}

:deep(.input-glass .van-cell) {
  background: transparent;
  color: #e5efff;
}

:deep(.input-glass .van-cell::after) {
  border-bottom-color: rgba(186, 230, 253, 0.24);
}

:deep(.input-glass .van-field__left-icon) {
  color: rgba(125, 211, 252, 0.55);
  font-size: 16px;
  margin-right: 2px;
  transition: color 0.2s;
}

:deep(.input-glass .van-cell:focus-within .van-field__left-icon) {
  color: rgba(125, 211, 252, 0.95);
  filter: drop-shadow(0 0 5px rgba(125, 211, 252, 0.55));
}

:deep(.input-glass .van-cell:focus-within) {
  background: rgba(14, 165, 233, 0.06);
}

:deep(.input-glass .van-field__control) {
  color: #f8fbff;
}

:deep(.input-glass .van-field__control::placeholder) {
  color: rgba(219, 234, 254, 0.58);
}

.login-action {
  margin: 14px 0 8px;
  position: relative;
  z-index: 1;
}

.login-btn {
  border: 1px solid rgba(125, 211, 252, 0.45) !important;
  animation: btnGlow 3.5s ease-in-out infinite;
}

.login-btn :deep(.van-button__text) {
  letter-spacing: 5px;
  font-weight: 700;
  font-size: 14px;
  text-shadow: 0 0 14px rgba(186, 230, 253, 0.7);
}

.btn-label {
  display: inline-block;
}

.seg-divider {
  margin: 12px 10px 6px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(125, 211, 252, 0.22), transparent);
  position: relative;
  z-index: 1;
}

.action-links {
  margin-top: 4px;
  position: relative;
  z-index: 1;
}

.cyber-btn {
  border: 1px solid rgba(125, 211, 252, 0.28) !important;
  background: rgba(14, 165, 233, 0.06) !important;
  color: rgba(186, 230, 253, 0.82) !important;
  font-size: 13px !important;
  letter-spacing: 1px !important;
}

.cyber-btn:active {
  background: rgba(14, 165, 233, 0.14) !important;
  border-color: rgba(125, 211, 252, 0.52) !important;
  color: #e0f2fe !important;
}

.forgot-row {
  text-align: right;
  padding: 6px 2px 0;
  position: relative;
  z-index: 1;
}

.txt-link {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  color: rgba(125, 211, 252, 0.58);
  text-decoration: underline;
  text-decoration-color: rgba(125, 211, 252, 0.2);
  text-underline-offset: 3px;
  padding: 4px 0;
  outline: none;
  transition: color 0.15s, text-decoration-color 0.15s;
  -webkit-tap-highlight-color: transparent;
}

.txt-link:active {
  color: rgba(186, 230, 253, 0.95);
  text-decoration-color: rgba(125, 211, 252, 0.6);
}

.rankings-entry {
  margin-top: 10px;
  position: relative;
  z-index: 1;
}

.rankings-entry-btn {
  color: rgba(251, 191, 36, 0.78) !important;
  border-color: rgba(251, 191, 36, 0.22) !important;
  background: rgba(251, 191, 36, 0.04) !important;
  font-size: 12px !important;
  letter-spacing: 0.5px !important;
}

.login-copyright {
  margin-top: 14px;
  text-align: center;
  font-size: 10px;
  color: rgba(148, 163, 184, 0.48);
  letter-spacing: 0.5px;
  position: relative;
  z-index: 1;
}

.icp-link {
  display: inline-block;
  margin-top: 5px;
  color: rgba(148, 163, 184, 0.62);
  text-decoration: none;
  -webkit-tap-highlight-color: transparent;
}

.icp-link:active {
  color: rgba(186, 230, 253, 0.9);
}

.copyright-arc {
  font-family: 'Orbitron', monospace;
  font-size: 9px;
  font-weight: 700;
  color: rgba(125, 211, 252, 0.5);
  letter-spacing: 2px;
}

.particles-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}

.particle {
  position: absolute;
  left: 0;
  top: 0;
  border-radius: 999px;
  will-change: transform;
}

.trail-segment {
  position: absolute;
  height: 2px;
  border-radius: 999px;
  transform-origin: left center;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.02), rgba(125, 211, 252, 0.45), rgba(186, 230, 253, 0.24));
  filter: blur(0.45px);
  pointer-events: none;
}

.particle-core {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background:
    conic-gradient(from 50deg, rgba(255, 255, 255, 0.26), rgba(147, 197, 253, 0.02) 22%, rgba(255, 255, 255, 0.24) 48%, rgba(147, 197, 253, 0.02) 76%, rgba(255, 255, 255, 0.2)),
    radial-gradient(circle at 33% 30%, rgba(255, 255, 255, 0.56), rgba(255, 255, 255, 0) 38%),
    radial-gradient(circle at 52% 50%, rgba(191, 219, 254, 0.34), rgba(59, 130, 246, 0.15) 70%, rgba(59, 130, 246, 0) 100%);
  border: 1px solid rgba(191, 219, 254, 0.52);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.22),
    inset 0 0 0 3px rgba(125, 211, 252, 0.2),
    0 0 14px rgba(96, 165, 250, 0.22);
  animation: discBreath 3.5s ease-in-out infinite;
}

.spark {
  position: absolute;
  border-radius: 999px;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(255, 255, 255, 0.95) 0%, rgba(253, 224, 71, 0.82) 45%, rgba(253, 224, 71, 0) 100%);
  box-shadow: 0 0 8px rgba(253, 224, 71, 0.55);
  pointer-events: none;
}

.bg-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(4px);
  z-index: 0;
}

.bg-orb--left {
  width: 260px;
  height: 260px;
  left: -80px;
  top: -30px;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.34), rgba(6, 182, 212, 0));
}

.bg-orb--right {
  width: 280px;
  height: 280px;
  right: -90px;
  bottom: -50px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.26), rgba(59, 130, 246, 0));
  animation: drift 10s ease-in-out infinite;
}

.bg-orb--left {
  animation: drift 11s ease-in-out infinite reverse;
}

@media (max-width: 420px) {
  .logo-area h1 {
    font-size: 20px;
    letter-spacing: 1.5px;
  }

  .login-card {
    padding: 20px 14px 16px;
    border-radius: 18px;
  }
}

@keyframes cardEnter {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes spinArc {
  to { transform: rotate(360deg); }
}

@keyframes btnGlow {
  0%, 100% {
    box-shadow: 0 0 12px rgba(14, 165, 233, 0.28), 0 4px 12px rgba(29, 78, 216, 0.22);
  }
  50% {
    box-shadow: 0 0 24px rgba(14, 165, 233, 0.6), 0 4px 18px rgba(29, 78, 216, 0.44), 0 0 40px rgba(14, 165, 233, 0.18);
  }
}

@keyframes discBreath {
  0%, 100% {
    box-shadow:
      inset 0 0 0 1px rgba(255, 255, 255, 0.18),
      inset 0 0 0 3px rgba(125, 211, 252, 0.12),
      0 0 8px rgba(96, 165, 250, 0.14);
    opacity: 0.72;
  }
  50% {
    box-shadow:
      inset 0 0 0 1px rgba(255, 255, 255, 0.38),
      inset 0 0 0 3px rgba(125, 211, 252, 0.45),
      0 0 22px rgba(96, 165, 250, 0.52),
      0 0 36px rgba(14, 165, 233, 0.22);
    opacity: 1;
  }
}

@keyframes titleReveal {
  from {
    opacity: 0;
    letter-spacing: 10px;
    filter: blur(6px);
  }
  to {
    opacity: 1;
    letter-spacing: 2px;
    filter: blur(0);
  }
}

@keyframes versionGlow {
  0%, 100% {
    border-color: rgba(125, 211, 252, 0.45);
    box-shadow: 0 0 5px rgba(14, 165, 233, 0.25);
    color: rgba(125, 211, 252, 0.9);
  }
  50% {
    border-color: rgba(125, 211, 252, 0.9);
    box-shadow: 0 0 12px rgba(14, 165, 233, 0.65), 0 0 22px rgba(14, 165, 233, 0.3);
    color: rgba(255, 255, 255, 0.95);
  }
}

@keyframes pulseRing {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.04);
  }
}

@keyframes drift {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(14px, -10px);
  }
}

@keyframes sweep {
  0% {
    transform: translateX(-45%) rotate(-6deg);
    opacity: 0;
  }
  12% {
    opacity: 1;
  }
  60% {
    opacity: 1;
  }
  100% {
    transform: translateX(42%) rotate(-6deg);
    opacity: 0;
  }
}

@keyframes cardSheen {
  0%,
  100% {
    transform: translateX(0) rotate(8deg);
    opacity: 0.16;
  }
  48% {
    opacity: 0.3;
  }
  62% {
    transform: translateX(185%) rotate(8deg);
    opacity: 0.08;
  }
}
</style>
