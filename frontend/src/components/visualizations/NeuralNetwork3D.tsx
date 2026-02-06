
import React, { useRef, useMemo, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Float, Text, Sphere, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';
import { useAgentStore } from '../../store/agentStore';

const PHI = (1 + Math.sqrt(5)) / 2;
const GOLDEN_ANGLE = 137.5 * (Math.PI / 180);

interface NodeProps {
    id: string;
    position: [number, number, number];
    color: string;
    label: string;
    activity: number; // 0 to 1
}

function HexNode({ position, color, label, activity }: NodeProps) {
    const meshRef = useRef<THREE.Mesh>(null);
    const [hovered, setHovered] = useState(false);

    useFrame((state) => {
        if (meshRef.current) {
            // Pulsing effect based on activity
            const pulse = Math.sin(state.clock.elapsedTime * 4 + activity * 10) * 0.1 + 0.9;
            meshRef.current.scale.setScalar(pulse * (hovered ? 1.2 : 1.0));

            // Rotation
            meshRef.current.rotation.y += 0.01;
        }
    });

    return (
        <group position={position}>
            <Float speed={2} rotationIntensity={0.5} floatIntensity={0.5}>
                <mesh
                    ref={meshRef}
                    onPointerOver={() => setHovered(true)}
                    onPointerOut={() => setHovered(false)}
                >
                    <cylinderGeometry args={[0.5, 0.5, 0.2, 6]} />
                    <meshStandardMaterial
                        color={color}
                        emissive={color}
                        emissiveIntensity={activity > 0.5 ? 2.0 : 0.5}
                        roughness={0.2}
                        metalness={0.8}
                    />
                </mesh>
            </Float>
            {hovered && (
                <Text
                    position={[0, 1, 0]}
                    fontSize={0.3}
                    color="white"
                    anchorX="center"
                    anchorY="middle"
                >
                    {label}
                </Text>
            )}
        </group>
    );
}

function ConnectionLines({ nodes }: { nodes: NodeProps[] }) {
    const lines = useMemo(() => {
        const points: THREE.Vector3[] = [];
        // Connect to center and nearby neighbors
        nodes.forEach((node, i) => {
            // To center
            if (i < 8) {
                points.push(new THREE.Vector3(0, 0, 0));
                points.push(new THREE.Vector3(...node.position));
            }

            // To some neighbors
            if (i > 0) {
                const prev = nodes[i - 1];
                points.push(new THREE.Vector3(...prev.position));
                points.push(new THREE.Vector3(...node.position));
            }
        });
        return points;
    }, [nodes]);

    return (
        <lineSegments>
            <bufferGeometry>
                <bufferAttribute
                    attach="attributes-position"
                    args={[new Float32Array(lines.flatMap(v => [v.x, v.y, v.z])), 3]}
                />
            </bufferGeometry>
            <lineBasicMaterial color="#38bdf8" opacity={0.1} transparent />
        </lineSegments>
    );
}

function NeuralHive() {
    const { agents } = useAgentStore();

    const nodes = useMemo(() => {
        const count = agents.length > 0 ? agents.length : 32;
        return Array.from({ length: count }).map((_, i) => {
            const r = 2.5 * Math.sqrt(i + 1);
            const theta = i * GOLDEN_ANGLE;

            return {
                id: agents[i]?.id || `node-${i}`,
                position: [
                    r * Math.cos(theta),
                    r * Math.sin(theta),
                    Math.sin(i * 0.5) * 2
                ] as [number, number, number],
                color: agents[i]?.status === 'active' ? '#38bdf8' : '#1e293b',
                label: agents[i]?.name || `Node ${i}`,
                activity: Math.random()
            };
        });
    }, [agents]);

    const hiveRef = useRef<THREE.Group>(null);
    useFrame((state) => {
        if (hiveRef.current) {
            hiveRef.current.rotation.z = state.clock.elapsedTime * 0.05;
        }
    });

    return (
        <group ref={hiveRef}>
            <ConnectionLines nodes={nodes} />
            {nodes.map((node) => (
                <HexNode key={node.id} {...node} />
            ))}

            {/* Central Core */}
            <Sphere args={[1.5, 64, 64]}>
                <MeshDistortMaterial
                    color="#0ea5e9"
                    emissive="#0369a1"
                    emissiveIntensity={0.5}
                    speed={2}
                    distort={0.4}
                    radius={1}
                />
            </Sphere>
        </group>
    );
}

export function NeuralNetwork3D() {
    return (
        <div className="w-full h-full min-h-[400px]">
            <Canvas camera={{ position: [0, 0, 25], fov: 45 }}>
                <color attach="background" args={['#000000']} />
                <ambientLight intensity={0.2} />
                <pointLight position={[10, 10, 10]} intensity={1} color="#38bdf8" />
                <pointLight position={[-10, -10, -10]} intensity={0.5} color="#818cf8" />

                <NeuralHive />

                <OrbitControls
                    enableZoom={true}
                    enablePan={false}
                    maxDistance={40}
                    minDistance={5}
                    autoRotate
                    autoRotateSpeed={0.5}
                />
            </Canvas>
        </div>
    );
}
