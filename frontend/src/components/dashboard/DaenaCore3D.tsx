
import { useRef, useEffect, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Sphere, Html } from '@react-three/drei';
import * as THREE from 'three';
import { api } from '../../services/api';

// Golden Ratio
const PHI = 1.618033988749895;

// Mock backup Departments if API fails during initial render
const DEPARTMENTS_MOCK = [
    { id: 'engineering', name: 'Engineering', color: '#3B82F6' },
    { id: 'sales', name: 'Sales', color: '#10B981' },
    { id: 'marketing', name: 'Marketing', "color": '#F59E0B' },
    { id: 'product', name: 'Product', "color": '#8B5CF6' },
    { id: 'legal', name: 'Legal', "color": '#EF4444' },
    { id: 'hr', name: 'HR', "color": '#EC4899' },
    { id: 'operations', name: 'Operations', "color": '#06B6D4' },
    { id: 'shadow', name: 'Shadow', "color": '#1F2937' },
];

// Fibonacci spiral position calculation
const getFibonacciPosition = (index: number, scale: number = 1) => {
    const angle = index * 137.5 * (Math.PI / 180); // Golden angle
    const radius = scale * Math.sqrt(index) * PHI;

    return {
        x: radius * Math.cos(angle),
        y: radius * Math.sin(angle),
        z: Math.sin(index * 0.5) * 2, // Slight 3D depth
    };
};

function DaenaCore({ onClick }: { onClick: () => void }) {
    const meshRef = useRef<THREE.Mesh>(null);
    const [hovered, setHovered] = useState(false);

    useFrame((state) => {
        if (meshRef.current) {
            meshRef.current.rotation.y += 0.005;
            meshRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.5) * 0.1;
        }
    });

    return (
        <group>
            {/* Core Sphere */}
            <mesh
                ref={meshRef}
                onClick={onClick}
                onPointerOver={() => setHovered(true)}
                onPointerOut={() => setHovered(false)}
            >
                <sphereGeometry args={[1.5, 32, 32]} />
                <meshStandardMaterial
                    color={hovered ? '#8B5CF6' : '#6366F1'}
                    emissive={hovered ? '#4C1D95' : '#312E81'}
                    emissiveIntensity={0.5}
                    roughness={0.2}
                    metalness={0.8}
                />
            </mesh>

            {/* Glow Effect */}
            <mesh>
                <sphereGeometry args={[2, 32, 32]} />
                <meshBasicMaterial
                    color="#6366F1"
                    transparent
                    opacity={0.1}
                />
            </mesh>

            {/* Label */}
            <Text
                position={[0, -2.5, 0]}
                fontSize={0.5}
                color="white"
                anchorX="center"
                anchorY="middle"
            >
                DAENA
            </Text>
        </group>
    );
}

function DepartmentHex({ dept, index, onClick }: { dept: any, index: number, onClick: (id: string) => void }) {
    const meshRef = useRef<THREE.Mesh>(null);
    const pos = getFibonacciPosition(index + 1, 3);
    const [hovered, setHovered] = useState(false);

    useFrame((state) => {
        if (meshRef.current) {
            meshRef.current.position.y = pos.y + Math.sin(state.clock.elapsedTime + index) * 0.2;
        }
    });

    return (
        <group position={[pos.x, pos.y, pos.z]}>
            {/* Hexagon */}
            <mesh
                ref={meshRef}
                onClick={(e) => { e.stopPropagation(); onClick(dept.id); }}
                onPointerOver={() => setHovered(true)}
                onPointerOut={() => setHovered(false)}
            >
                <cylinderGeometry args={[1, 1, 0.5, 6]} />
                <meshStandardMaterial
                    color={dept.color}
                    emissive={dept.color}
                    emissiveIntensity={hovered ? 0.5 : 0.2}
                    roughness={0.3}
                    metalness={0.7}
                />
            </mesh>

            {/* Connection line to center */}
            <line>
                <bufferGeometry>
                    <bufferAttribute
                        attach="attributes-position"
                        args={[new Float32Array([0, 0, 0, -pos.x, -pos.y, -pos.z]), 3]}
                    />
                </bufferGeometry>
                <lineBasicMaterial color="#4B5563" opacity={0.3} transparent />
            </line>

            {/* Label */}
            <Text
                position={[0, -1.5, 0]}
                fontSize={0.3}
                color="white"
                anchorX="center"
                anchorY="middle"
            >
                {dept.name}
            </Text>

            {/* Agent count badge */}
            <Text
                position={[0.8, 0.5, 0]}
                fontSize={0.25}
                color="#10B981"
                anchorX="center"
                anchorY="middle"
            >
                {dept.agents || 6}
            </Text>
        </group>
    );
}

function ConnectionLines() { return null; } // Simplify for now

export function DaenaCore3D() {
    const [selectedDept, setSelectedDept] = useState<string | null>(null);
    const [departments, setDepartments] = useState<any[]>(DEPARTMENTS_MOCK);

    useEffect(() => {
        // Ideally fetch real structure here
        const fetchStructure = async () => {
            try {
                // const data = await api.dashboard.getSunflowerData();
                // setDepartments(data.departments);
            } catch (e) { }
        }
        fetchStructure();
    }, [])

    return (
        <div className="w-full h-screen bg-gray-900 relative overflow-hidden">
            {/* UI Overlay */}
            <div className="absolute top-4 left-4 z-10 pointer-events-none">
                <h1 className="text-2xl font-bold text-white drop-shadow-lg">DAENA OS</h1>
                <p className="text-gray-400 drop-shadow-md">Autonomous Agent Command Center</p>
            </div>

            <div className="absolute top-4 right-4 z-10 flex gap-2 pointer-events-none">
                {/* Badges or status indicators */}
                <div className="bg-gray-800/80 backdrop-blur px-3 py-1 rounded text-green-400 border border-green-500/30">
                    System Active
                </div>
            </div>

            {/* 3D Canvas */}
            <Canvas camera={{ position: [0, 0, 20], fov: 60 }}>
                <ambientLight intensity={0.5} />
                <pointLight position={[10, 10, 10]} intensity={1} />
                <pointLight position={[-10, -10, -10]} intensity={0.5} color="#8B5CF6" />

                {/* Daena Core */}
                <DaenaCore onClick={() => setSelectedDept('core')} />

                {/* Departments */}
                {departments.map((dept, index) => (
                    <DepartmentHex
                        key={dept.id}
                        dept={dept}
                        index={index}
                        onClick={(id) => setSelectedDept(id)}
                    />
                ))}

                {/* Controls */}
                <OrbitControls
                    enablePan={true}
                    enableZoom={true}
                    enableRotate={true}
                    minDistance={10}
                    maxDistance={50}
                />
            </Canvas>

            {/* Selected Department Panel */}
            {selectedDept && (
                <div className="absolute bottom-4 left-4 right-4 bg-gray-800/90 backdrop-blur rounded-lg p-4 z-10 border-t border-gray-700 animate-slide-up">
                    <div className="flex justify-between items-center">
                        <div>
                            <h2 className="text-xl font-bold text-white capitalize">
                                {selectedDept === 'core' ? 'DAENA Core' : departments.find(d => d.id === selectedDept)?.name}
                            </h2>
                            <p className="text-gray-400">
                                {selectedDept === 'core' ? 'Central Intelligence & Coordination' : 'Departmental Operations Active'}
                            </p>
                        </div>
                        <button
                            onClick={() => setSelectedDept(null)}
                            className="text-gray-400 hover:text-white px-3 py-1"
                        >
                            Close
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
