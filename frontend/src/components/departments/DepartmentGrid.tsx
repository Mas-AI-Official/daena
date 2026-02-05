import { useEffect, useState } from 'react';
import { Hexagon, Users, Loader2, Target, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { departmentsApi } from '../../services/api/departments';
import type { Department } from '../../services/api/departments';

import { useNavigate } from 'react-router-dom';

export function DepartmentGrid() {
    const [departments, setDepartments] = useState<Department[]>([]);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchDepartments = async () => {
            try {
                const data = await departmentsApi.getAll(true);
                const sorted = data.departments.sort((a, b) => a.sunflower_index - b.sunflower_index);
                setDepartments(sorted);
            } catch (error) {
                console.error('Failed to fetch departments:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchDepartments();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Loader2 className="w-8 h-8 animate-spin text-primary-400" />
            </div>
        )
    }

    return (
        <div className="space-y-8 animate-fade-in pb-12">
            <div>
                <h1 className="text-3xl font-display font-medium text-white mb-2 flex items-center gap-3">
                    <Hexagon className="w-8 h-8 text-status-success" />
                    Departments
                </h1>
                <p className="text-starlight-300 max-w-2xl">
                    Sunflower Architecture • 8 Core Autonomous Divisions
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {departments.map((dept) => (
                    <DepartmentCard key={dept.id} department={dept} onClick={() => navigate(`/departments/${dept.id}`)} />
                ))}
            </div>
        </div>
    );
}

function DepartmentCard({ department, onClick }: { department: Department, onClick: () => void }) {
    // Generate a style for the glow based on provided color or default
    const glowStyle = {
        boxShadow: `0 0 40px -20px ${department.color || '#6366F1'}40` // 40 = 25% opacity
    };

    return (
        <Card
            className="group cursor-pointer hover:-translate-y-1 transition-all duration-300 relative overflow-hidden"
            onClick={onClick}
            style={glowStyle}
        >
            {/* Top Color Line */}
            <div className="absolute top-0 left-0 right-0 h-1 transition-all duration-300 group-hover:h-1.5" style={{ backgroundColor: department.color || '#6366F1' }} />

            <CardHeader className="pb-3 border-b-0">
                <div className="flex justify-between items-start">
                    <CardTitle className="text-lg font-display text-white truncate pr-2 group-hover:text-starlight-100 transition-colors" title={department.name}>
                        {department.name}
                    </CardTitle>
                    <div className="h-6 w-6 rounded-lg bg-midnight-200 border border-white/10 flex items-center justify-center text-[10px] font-bold text-starlight-300">
                        {department.sunflower_index}
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-6 pt-1">
                <p className="text-sm text-starlight-300 line-clamp-2 h-10 leading-relaxed">
                    {department.description}
                </p>

                {/* Metrics */}
                <div className="grid grid-cols-2 gap-2 p-3 rounded-xl bg-midnight-200/50 border border-white/5">
                    <div className="text-center">
                        <div className="flex items-center justify-center gap-1.5 text-xs text-starlight-300 mb-0.5">
                            <Users className="w-3 h-3" /> Agents
                        </div>
                        <span className="text-lg font-display font-medium text-white">{department.agents_count}</span>
                    </div>
                    <div className="text-center border-l border-white/5">
                        <div className="flex items-center justify-center gap-1.5 text-xs text-starlight-300 mb-0.5">
                            <Target className="w-3 h-3" /> Focus
                        </div>
                        <span className="text-lg font-display font-medium text-white">{(department.agents || []).length > 0 ? "Active" : "Idle"}</span>
                    </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                    <div className="flex -space-x-2">
                        {(department.agents || []).slice(0, 3).map(agent => (
                            <div key={agent.id} className="w-7 h-7 rounded-full bg-midnight-300 border border-white/10 flex items-center justify-center text-[10px] text-starlight-200 relative group/avatar">
                                {agent.name.charAt(0)}
                            </div>
                        ))}
                    </div>

                    <div className="flex items-center gap-1 text-xs font-medium text-primary-400 opacity-0 group-hover:opacity-100 transition-opacity transform translate-x-2 group-hover:translate-x-0 duration-300">
                        View Sector <ArrowRight className="w-3 h-3" />
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
