# CT665 สอบ: ให้บริการเว็บด้วย Kubernetes (iam-548)

ระบบเว็บ 4 บริการ ทำงานบนคลัสเตอร์ Kubernetes 3 node (kubeadm + Flannel บน VMware)
รหัสนักศึกษา 68130548 จึงใช้ xxx = **548**

| URL | Deployment | หน้าที่ |
|---|---|---|
| `www.iam-548.com` (และ `www.id-548.com`) | **portal-548** | แสดงรูป ชื่อ และรหัสนักศึกษา |
| `www.iam-548.com/research` | **app-research** | แสดงสรุปงานวิจัยที่นำเสนอในวิชาสัมมนา |
| `www.iam-548.com/api-548/<ข้อความ>` | **api-548** | แสดง `<ข้อความ>` ตัวใหญ่กลางจอ |
| `admin.iam-548.com` | **admin-548** | หน้าปุ่มเลือกแก้ไขข้อมูลของ portal และ research |

ทุกหน้ามีเมนูด้านบนสำหรับไปหน้าอื่น

## สถาปัตยกรรม

```
Browser (Windows)
  │  hosts: www.iam-548.com, www.id-548.com, admin.iam-548.com → 192.168.88.130
  ▼
k8s-worker2:80  NGINX Ingress Controller (hostNetwork)
  ├─ www-ingress    host www.iam-548.com / www.id-548.com
  │    /research  → Service app-research → Deployment app-research (2 pods) ← ConfigMap research-data
  │    /api-548   → Service api-548      → Deployment api-548      (2 pods)
  │    /          → Service portal-548   → Deployment portal-548   (2 pods) ← ConfigMap portal-data
  └─ admin-ingress  host admin.iam-548.com
       /          → Service admin-548    → Deployment admin-548    (1 pod)
                                            │ ServiceAccount admin-548 + Role (RBAC)
                                            ▼
                                     Kubernetes API: patch ConfigMap portal-data / research-data
                                                     + rollout restart portal-548 / app-research

คลัสเตอร์: k8s-control 192.168.88.128 (control-plane)
           k8s-worker1 192.168.88.129, k8s-worker2 192.168.88.130 (worker)
```

1. เบราว์เซอร์แปลงชื่อโดเมนเป็น IP `192.168.88.130` จากไฟล์ hosts
2. NGINX Ingress Controller รันแบบ hostNetwork บน k8s-worker2 รับ request ที่ port 80 แล้วเลือก Service จากชื่อ host และ path
3. Service (ClusterIP) กระจาย request ไปยัง pod ของ Deployment นั้น ซึ่งอยู่บน worker ทั้ง 2 เครื่อง
4. ข้อมูลของ portal และ research เก็บใน ConfigMap แล้ว mount เข้า pod ที่ `/data`
5. admin-548 แก้ข้อมูลผ่าน Kubernetes API ด้วย ServiceAccount ของตัวเอง
   - บันทึกลง ConfigMap แล้วสั่ง rollout restart ให้ Deployment ปลายทาง
   - pod ใหม่จึงเห็นข้อมูลใหม่ภายในไม่กี่วินาที
   - ข้อมูลอยู่ใน etcd ไม่ผูกกับ node ใด จึงใช้ได้แม้ pod กระจายอยู่หลาย node

แอปทั้ง 4 ตัวเขียนด้วย Python (standard library เท่านั้น) รันบน image `python:3.12-alpine`
โค้ดเก็บใน ConfigMap แล้ว mount เข้า container ที่ `/app` จึงไม่ต้อง build image และไม่ต้องใช้ registry

## ไฟล์ในโปรเจกต์

```
.
├── kustomization.yaml          รวม manifest ทั้งหมด และสร้าง ConfigMap จากไฟล์โค้ดและข้อมูล
├── k8s/
│   ├── 00-namespace.yaml       Namespace iam-548 + ConfigMap site-config (URL, API path)
│   ├── 10-portal.yaml          Deployment + Service ของ portal-548
│   ├── 20-research.yaml        Deployment + Service ของ app-research
│   ├── 30-api.yaml             Deployment + Service ของ api-548
│   ├── 40-admin.yaml           ServiceAccount + Role + RoleBinding + Deployment + Service ของ admin-548
│   └── 50-ingress.yaml         Ingress ของ www และ admin
├── apps/
│   ├── common.py               เมนูและสีที่ทุกแอปใช้ร่วมกัน
│   ├── portal/app.py
│   ├── research/app.py
│   ├── api/app.py
│   └── admin/app.py
├── data/                       ข้อมูลตั้งต้น
│   ├── portal.json             ชื่อ รหัส รายวิชา
│   ├── photo.jpg               รูปนักศึกษา
│   └── research.json           หัวข้อและสรุปงานวิจัย
├── hosts/hosts.example         ตัวอย่างไฟล์ /etc/hosts
└── scripts/
    ├── deploy.sh               deploy ทั้งหมด
    ├── verify.sh               ตรวจสถานะและทดสอบทุก route
    └── cleanup.sh              ลบทั้งหมด
```

## รายละเอียด manifest

**ConfigMap** สร้างด้วย `configMapGenerator` ของ kustomize (มีอยู่ใน kubectl)
- ConfigMap ของโค้ด (`*-code`, `app-common`) มี hash ต่อท้ายชื่อ
  แก้ไฟล์ `.py` แล้วสั่ง `kubectl apply -k .` ใหม่ Deployment จะ rollout เอง
- ConfigMap ของข้อมูล (`portal-data`, `research-data`) ใช้ชื่อคงที่ เพราะ admin-548 แก้ด้วยชื่อนี้
  ถ้าสั่ง `kubectl apply -k .` ใหม่ ข้อมูลจะกลับเป็นค่าในโฟลเดอร์ `data/`

**Deployment**
- portal-548, app-research, api-548 ใช้ 2 replicas ส่วน admin-548 ใช้ 1 replica
- ทุกตัวมี readinessProbe และ livenessProbe ที่ `/healthz` และกำหนด resources requests/limits

**RBAC ของ admin-548** ให้สิทธิ์น้อยที่สุดที่ต้องใช้
- `get`, `patch` เฉพาะ ConfigMap `portal-data` และ `research-data`
- `get`, `patch` เฉพาะ Deployment `portal-548` และ `app-research` (ใช้สั่ง rollout restart)
- ทำอย่างอื่นไม่ได้ เช่น ลบ pod หรือแก้ ConfigMap ตัวอื่น ตรวจได้ด้วย `kubectl auth can-i`

**Ingress** แยกเป็น 2 ตัว
- `www-ingress` ส่ง `/research`, `/api-548` และ `/` ไปยัง Service ของแต่ละแอป
  ใช้ได้ทั้ง `www.iam-548.com` และ `www.id-548.com`
- `admin-ingress` ส่ง `admin.iam-548.com` ไปที่ admin-548
  เพิ่ม `proxy-body-size: 2m` ให้อัปโหลดรูปได้ เฉพาะ host นี้

## ขั้นตอนการ deploy

ทำบนเครื่อง `k8s-control`

### 1. Clone repository

```bash
git clone https://github.com/68130548-Kittaporn/k8s-exam-548.git
cd k8s-exam-548
```

### 2. NGINX Ingress Controller

คลัสเตอร์นี้ติดตั้ง ingress-nginx แบบ hostNetwork ไว้แล้ว ตรวจสอบด้วย

```bash
kubectl get ingressclass
kubectl -n ingress-nginx get pod -o wide
```

ถ้ายังไม่มี ให้ติดตั้งแล้ว patch ให้ใช้ hostNetwork (`scripts/deploy.sh` ทำให้อัตโนมัติ)

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/baremetal/deploy.yaml
kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type=json -p='[
  {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
  {"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
```

กำหนดให้ controller อยู่บน k8s-worker2 เสมอ IP ในไฟล์ hosts จะได้ไม่เปลี่ยน

```bash
kubectl -n ingress-nginx patch deploy ingress-nginx-controller \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/hostname":"k8s-worker2"}}}}}'
```

### 3. Deploy แอป

```bash
kubectl kustomize . | less      # ดู manifest ที่จะถูกสร้าง
kubectl apply -k .
kubectl -n iam-548 rollout status deployment/portal-548
kubectl -n iam-548 rollout status deployment/app-research
kubectl -n iam-548 rollout status deployment/api-548
kubectl -n iam-548 rollout status deployment/admin-548
```

หรือรันทั้งหมดด้วยสคริปต์

```bash
bash scripts/deploy.sh
```

### 4. แก้ไฟล์ hosts ของเครื่องที่ใช้เปิดเว็บ

- Windows: เปิด Notepad แบบ Administrator แล้วแก้ `C:\Windows\System32\drivers\etc\hosts`
- Linux: แก้ `/etc/hosts`

เพิ่มบรรทัดนี้

```
192.168.88.130   www.iam-548.com www.id-548.com admin.iam-548.com
```

ตัวอย่างไฟล์เต็มอยู่ที่ `hosts/hosts.example`

### 5. ตรวจสอบการทำงาน

```bash
kubectl get nodes -o wide
kubectl -n iam-548 get all -o wide
kubectl -n iam-548 get ingress,configmap,sa,role,rolebinding
kubectl -n iam-548 describe ingress www-ingress admin-ingress
kubectl -n iam-548 get endpoints
kubectl auth can-i patch configmap/portal-data -n iam-548 --as=system:serviceaccount:iam-548:admin-548
kubectl auth can-i delete pods -n iam-548 --as=system:serviceaccount:iam-548:admin-548
```

ทดสอบด้วย curl

```bash
curl http://www.iam-548.com/
curl http://www.iam-548.com/research
curl http://www.iam-548.com/api-548/Hello%20I%27m%20June
curl http://admin.iam-548.com/
```

เปิด `admin.iam-548.com` เลือก **แก้ไข Research** แก้ข้อความแล้วกด Save
รอประมาณ 10-20 วินาที แล้วเปิด `www.iam-548.com/research` จะเห็นข้อความใหม่

ตรวจทั้งหมดในครั้งเดียวด้วยสคริปต์

```bash
bash scripts/verify.sh
```

## ลบออก

```bash
bash scripts/cleanup.sh
```
