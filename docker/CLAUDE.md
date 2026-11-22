# 플랫폼 이미지 빌드

- 각 Dockerfile의 빌드 컨텍스트와 target은 운영 문서와 대조한다. [이미지 예시](../configs/platform-images.env.example)와 Kubernetes의 실제 이미지 참조도 함께 확인한다.
- 로컬 k3d 노드 아키텍처는 ARM64다. 의존성 핀과 검증용 checksum을 함께 관리하고, 자격증명이나 `.env`를 이미지 레이어에 포함하지 않는다.
- 이미지 빌드, k3d 반입, 실제 배포는 각각 따로 검증한다.
