import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Line, Sphere, Box, Cone, Cylinder } from '@react-three/drei';
import * as THREE from 'three';

interface DronePosition {
  frame: number;
  timestamp: number;
  latitude: number;
  longitude: number;
  elevation: number;
}

interface ReferencePoint {
  latitude: number;
  longitude: number;
  elevation: number;
  point_type: string;
}

interface Airport3DVisualizationProps {
  dronePositions: DronePosition[];
  referencePoints: { [key: string]: ReferencePoint };
}

// Convert GPS coordinates to local 3D coordinates
function gpsTo3D(lat: number, lon: number, elevation: number, center: { lat: number, lon: number, elevation: number }) {
  // Convert to meters from center point
  const x = (lon - center.lon) * 111000 * Math.cos((center.lat * Math.PI) / 180);
  const z = -(lat - center.lat) * 111000; // Negative to match typical 3D coordinate system
  const y = elevation - center.elevation;
  
  return { x: x / 10, y: y / 10, z: z / 10 }; // Scale down for better visualization
}

function Runway({ center }: { center: { lat: number, lon: number, elevation: number } }) {
  // Create a runway - typically 2500m long, 45m wide
  const runwayLength = 250; // Scaled down
  const runwayWidth = 4.5;
  
  return (
    <group>
      {/* Main runway surface */}
      <Box args={[runwayLength, 0.1, runwayWidth]} position={[0, 0, 0]}>
        <meshStandardMaterial color="#2a2a2a" />
      </Box>
      
      {/* Centerline markings */}
      <Box args={[runwayLength, 0.11, 0.3]} position={[0, 0.01, 0]}>
        <meshStandardMaterial color="#ffffff" />
      </Box>
      
      {/* Runway threshold markings */}
      {[-runwayLength/2 + 5, runwayLength/2 - 5].map((x, i) => (
        <Box key={i} args={[3, 0.11, runwayWidth * 0.8]} position={[x, 0.01, 0]}>
          <meshStandardMaterial color="#ffffff" />
        </Box>
      ))}
    </group>
  );
}

function PAPILight({ position, color, lightName }: { 
  position: [number, number, number], 
  color: string, 
  lightName: string 
}) {
  return (
    <group position={position}>
      {/* Light pole */}
      <Cylinder args={[0.05, 0.08, 3]} position={[0, 1.5, 0]}>
        <meshStandardMaterial color="#444444" />
      </Cylinder>
      
      {/* Light fixture base */}
      <Box args={[0.8, 0.3, 0.4]} position={[0, 3.2, 0]}>
        <meshStandardMaterial color="#333333" />
      </Box>
      
      {/* Light lens/bulb */}
      <Sphere args={[0.25]} position={[0, 3.2, 0.3]}>
        <meshStandardMaterial 
          color={color} 
          emissive={color} 
          emissiveIntensity={0.6}
          transparent
          opacity={0.9}
        />
      </Sphere>
      
      {/* Light beam representation */}
      <Cone args={[0.3, 1.5]} position={[0, 3.2, 1]} rotation={[Math.PI / 2, 0, 0]}>
        <meshStandardMaterial 
          color={color} 
          transparent 
          opacity={0.2} 
          emissive={color}
          emissiveIntensity={0.1}
        />
      </Cone>
      
      {/* Light label */}
      <Text
        position={[0, 4, 0]}
        fontSize={0.5}
        color="#ffffff"
        anchorX="center"
        anchorY="middle"
      >
        {lightName}
      </Text>
    </group>
  );
}

function PAPILights({ referencePoints, center }: { 
  referencePoints: { [key: string]: ReferencePoint }, 
  center: { lat: number, lon: number, elevation: number } 
}) {
  const papiLights = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'];
  
  return (
    <group>
      {papiLights.map((lightName) => {
        const light = referencePoints[lightName];
        if (!light) return null;
        
        const pos3d = gpsTo3D(light.latitude, light.longitude, light.elevation, center);
        const color = {
          'PAPI_A': '#ef4444',
          'PAPI_B': '#f97316',
          'PAPI_C': '#eab308', 
          'PAPI_D': '#22c55e'
        }[lightName] || '#ffffff';
        
        return (
          <PAPILight
            key={lightName}
            position={[pos3d.x, pos3d.y, pos3d.z]}
            color={color}
            lightName={lightName}
          />
        );
      })}
    </group>
  );
}

function TouchPoint({ referencePoints, center }: { 
  referencePoints: { [key: string]: ReferencePoint }, 
  center: { lat: number, lon: number, elevation: number } 
}) {
  const touchPoint = referencePoints.TOUCH_POINT;
  if (!touchPoint) return null;
  
  const pos3d = gpsTo3D(touchPoint.latitude, touchPoint.longitude, touchPoint.elevation, center);
  
  return (
    <group>
      {/* Touch point marker */}
      <Sphere args={[0.8]} position={[pos3d.x, pos3d.y + 0.5, pos3d.z]}>
        <meshStandardMaterial color="#ff0000" />
      </Sphere>
      
      {/* Touch point label */}
      <Text
        position={[pos3d.x, pos3d.y + 2, pos3d.z]}
        fontSize={1}
        color="#ffffff"
        anchorX="center"
        anchorY="middle"
      >
        TOUCH POINT
      </Text>
    </group>
  );
}

function DroneIcon({ position, color, label, isAnimated = false }: { 
  position: THREE.Vector3, 
  color: string, 
  label: string,
  isAnimated?: boolean 
}) {
  const droneRef = useRef<THREE.Group>(null);
  
  useFrame((state) => {
    if (isAnimated && droneRef.current) {
      // Add gentle hovering animation
      droneRef.current.rotation.y += 0.01;
      droneRef.current.position.y = position.y + Math.sin(state.clock.elapsedTime * 2) * 0.2;
    }
  });
  
  return (
    <group ref={droneRef} position={position}>
      {/* Drone body */}
      <Box args={[1.5, 0.3, 1.5]} position={[0, 0, 0]}>
        <meshStandardMaterial color={color} />
      </Box>
      
      {/* Drone arms */}
      <Box args={[3, 0.1, 0.2]} position={[0, 0.1, 0]}>
        <meshStandardMaterial color="#666666" />
      </Box>
      <Box args={[0.2, 0.1, 3]} position={[0, 0.1, 0]}>
        <meshStandardMaterial color="#666666" />
      </Box>
      
      {/* Propellers */}
      {[[-1.2, 0.2, -1.2], [1.2, 0.2, -1.2], [-1.2, 0.2, 1.2], [1.2, 0.2, 1.2]].map((pos, i) => (
        <Cylinder key={i} args={[0.4, 0.4, 0.05]} position={pos as [number, number, number]}>
          <meshStandardMaterial color="#333333" />
        </Cylinder>
      ))}
      
      {/* Camera gimbal */}
      <Sphere args={[0.3]} position={[0, -0.4, 0]}>
        <meshStandardMaterial color="#222222" />
      </Sphere>
      
      {/* Label */}
      <Text
        position={[0, 1.5, 0]}
        fontSize={0.4}
        color="#ffffff"
        anchorX="center"
        anchorY="middle"
      >
        {label}
      </Text>
    </group>
  );
}

function DroneFlightPath({ dronePositions, center }: { 
  dronePositions: DronePosition[], 
  center: { lat: number, lon: number, elevation: number } 
}) {
  const pathPoints = useMemo(() => {
    return dronePositions.map(pos => {
      const pos3d = gpsTo3D(pos.latitude, pos.longitude, pos.elevation, center);
      return new THREE.Vector3(pos3d.x, pos3d.y, pos3d.z);
    });
  }, [dronePositions, center]);
  
  if (pathPoints.length < 2) return null;
  
  return (
    <group>
      {/* Flight path line */}
      <Line
        points={pathPoints}
        color="#00ffff"
        lineWidth={3}
      />
      
      {/* Drone start position */}
      {pathPoints.length > 0 && (
        <DroneIcon 
          position={pathPoints[0]} 
          color="#00ff00" 
          label="START"
        />
      )}
      
      {/* Drone end position */}
      {pathPoints.length > 1 && (
        <DroneIcon 
          position={pathPoints[pathPoints.length - 1]} 
          color="#ff0000" 
          label="END"
        />
      )}
      
      {/* Animated drone position */}
      <AnimatedDrone pathPoints={pathPoints} />
    </group>
  );
}

function AnimatedDrone({ pathPoints }: { pathPoints: THREE.Vector3[] }) {
  const droneRef = useRef<THREE.Group>(null);
  const progressRef = useRef(0);
  
  useFrame((state) => {
    if (!droneRef.current || pathPoints.length < 2) return;
    
    // Animate drone along the path
    progressRef.current = (progressRef.current + 0.002) % 1;
    const index = Math.floor(progressRef.current * (pathPoints.length - 1));
    const nextIndex = Math.min(index + 1, pathPoints.length - 1);
    const localProgress = (progressRef.current * (pathPoints.length - 1)) % 1;
    
    const currentPos = pathPoints[index];
    const nextPos = pathPoints[nextIndex];
    
    if (currentPos && nextPos) {
      droneRef.current.position.lerpVectors(currentPos, nextPos, localProgress);
      // Add gentle hovering animation
      droneRef.current.position.y += Math.sin(state.clock.elapsedTime * 3) * 0.3;
      // Rotate drone as it moves
      droneRef.current.rotation.y += 0.02;
    }
  });
  
  return (
    <group ref={droneRef}>
      {/* Animated drone body */}
      <Box args={[1.2, 0.25, 1.2]} position={[0, 0, 0]}>
        <meshStandardMaterial color="#ffff00" emissive="#ffff00" emissiveIntensity={0.2} />
      </Box>
      
      {/* Animated drone arms */}
      <Box args={[2.5, 0.08, 0.15]} position={[0, 0.08, 0]}>
        <meshStandardMaterial color="#555555" />
      </Box>
      <Box args={[0.15, 0.08, 2.5]} position={[0, 0.08, 0]}>
        <meshStandardMaterial color="#555555" />
      </Box>
      
      {/* Animated propellers */}
      {[[-1, 0.15, -1], [1, 0.15, -1], [-1, 0.15, 1], [1, 0.15, 1]].map((pos, i) => (
        <Cylinder key={i} args={[0.3, 0.3, 0.04]} position={pos as [number, number, number]}>
          <meshStandardMaterial color="#222222" />
        </Cylinder>
      ))}
      
      {/* Camera gimbal */}
      <Sphere args={[0.2]} position={[0, -0.3, 0]}>
        <meshStandardMaterial color="#111111" />
      </Sphere>
    </group>
  );
}

function Scene({ dronePositions, referencePoints }: Airport3DVisualizationProps) {
  // Calculate center point for coordinate conversion
  const center = useMemo(() => {
    if (dronePositions.length === 0) {
      return { lat: 48.8650, lon: 17.9867, elevation: 150 };
    }
    
    const avgLat = dronePositions.reduce((sum, pos) => sum + pos.latitude, 0) / dronePositions.length;
    const avgLon = dronePositions.reduce((sum, pos) => sum + pos.longitude, 0) / dronePositions.length;
    const avgElev = dronePositions.reduce((sum, pos) => sum + pos.elevation, 0) / dronePositions.length;
    
    return { lat: avgLat, lon: avgLon, elevation: avgElev };
  }, [dronePositions]);
  
  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.6} />
      <directionalLight position={[50, 50, 25]} intensity={1} castShadow />
      <pointLight position={[0, 50, 0]} intensity={0.5} />
      
      {/* Ground plane */}
      <Box args={[500, 0.1, 500]} position={[0, -5, 0]}>
        <meshStandardMaterial color="#2d5a27" />
      </Box>
      
      {/* Airport elements */}
      <Runway center={center} />
      <PAPILights referencePoints={referencePoints} center={center} />
      <TouchPoint referencePoints={referencePoints} center={center} />
      <DroneFlightPath dronePositions={dronePositions} center={center} />
      
      {/* Coordinate axes for reference */}
      <Line points={[[-50, 0, 0], [50, 0, 0]]} color="#ff0000" />
      <Line points={[[0, -5, 0], [0, 50, 0]]} color="#00ff00" />
      <Line points={[[0, 0, -50], [0, 0, 50]]} color="#0000ff" />
    </>
  );
}

export default function Airport3DVisualization({ dronePositions, referencePoints }: Airport3DVisualizationProps) {
  return (
    <div className="w-full h-96 bg-black rounded-lg overflow-hidden">
      <Canvas camera={{ position: [100, 50, 100], fov: 50 }}>
        <Scene dronePositions={dronePositions} referencePoints={referencePoints} />
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          maxPolarAngle={Math.PI / 2}
        />
      </Canvas>
    </div>
  );
}