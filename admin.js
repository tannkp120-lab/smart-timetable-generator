// --- Admin Components ---

// Using React hooks from the global scope
const { useState } = React;

const ManagementComponent = ({ title, existingItems, formFields, apiEndpoint, onAddData, isLoading, apiError }) => {
    const [formData, setFormData] = useState({});
    
    const handleSubmit = async (e) => {
        e.preventDefault();
        const success = await onAddData(apiEndpoint, formData);
        if (success) {
            setFormData({}); // Clear form only on success
        }
    };

    return (
        <div className="grid md:grid-cols-2 gap-8 mt-6">
            <div className="bg-white p-6 rounded-lg shadow-md">
                <h3 className="text-xl font-bold mb-4">Add New {title}</h3>
                <form onSubmit={handleSubmit} className="space-y-4">
                    {formFields.map(field => (
                        <div key={field.name}>
                            <label className="text-sm font-medium">{field.label}</label>
                            {field.type === 'select' ? (
                                <select name={field.name} value={formData[field.name] || ''} onChange={e => setFormData({...formData, [field.name]: e.target.value})} required className="w-full p-2 border rounded-md mt-1">
                                    <option value="">Select...</option>
                                    {field.options.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                                </select>
                            ) : (
                                <input type={field.type} name={field.name} value={formData[field.name] || ''} min={field.min} onChange={e => setFormData({...formData, [field.name]: e.target.value})} placeholder={field.placeholder} required className="w-full p-2 border rounded-md mt-1" />
                            )}
                        </div>
                    ))}
                    <button type="submit" disabled={isLoading} className="w-full bg-blue-500 text-white p-2 rounded-md hover:bg-blue-600 disabled:bg-gray-400">
                        {isLoading ? 'Adding...' : `Add ${title}`}
                    </button>
                    {apiError && <p className="text-red-500 text-sm mt-2">{apiError}</p>}
                </form>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md">
                <h3 className="text-xl font-bold mb-4">Existing {title}s</h3>
                <ul className="space-y-2 max-h-96 overflow-y-auto">{existingItems}</ul>
            </div>
        </div>
    );
};

const ManagementTab = ({ activeTab, allData, onAddData, isLoading, apiError }) => {
    if (activeTab === 'generate') return null;
    
    const commonProps = { onAddData, isLoading, apiError };
    
    switch(activeTab) {
        case 'teachers':
            return <ManagementComponent title="Teacher" {...commonProps} apiEndpoint="teachers" existingItems={allData.teachers?.map(t => <li key={t.id} className="p-2 bg-gray-100 rounded-md">{t.name}</li>)} formFields={[{ name: 'name', label: 'Teacher Name', type: 'text', placeholder: "e.g., Dr. Smith" }]} />
        case 'courses':
             return <ManagementComponent title="Course" {...commonProps} apiEndpoint="courses" existingItems={allData.courses?.map(c => <li key={c.id} className="p-2 bg-gray-100 rounded-md"><strong>{c.name}</strong> ({c.teacher_name}) - L: {c.lectures_per_week}, P: {c.practicals_per_week}</li>)} formFields={[ { name: 'name', label: 'Course Name', type: 'text', placeholder: 'e.g., Intro to AI' }, { name: 'teacher_id', label: 'Teacher', type: 'select', options: allData.teachers?.map(t => ({ value: t.id, label: t.name })) || [] }, { name: 'class_id', label: 'Class', type: 'select', options: allData.classes?.map(c => ({ value: c.id, label: c.name })) || [] }, { name: 'division_id', label: 'Division', type: 'select', options: allData.divisions?.map(d => ({ value: d.id, label: d.name })) || [] }, { name: 'lectures_per_week', label: 'Lectures/Week', type: 'number', min: 0 }, { name: 'practicals_per_week', label: 'Practicals/Week', type: 'number', min: 0 } ]} />
        case 'rooms':
            return <ManagementComponent title="Room" {...commonProps} apiEndpoint="rooms" existingItems={allData.rooms?.map(r => <li key={r.id} className="p-2 bg-gray-100 rounded-md"><strong>{r.name}</strong> ({r.type}) - Cap: {r.capacity}</li>)} formFields={[ { name: 'name', label: 'Room Name', type: 'text', placeholder: 'e.g., Room 103' }, { name: 'capacity', label: 'Capacity', type: 'number', min: 1 }, { name: 'type', label: 'Room Type', type: 'select', options: [{value: 'Lecture', label: 'Lecture'}, {value: 'Lab', label: 'Lab'}] } ]} />
        case 'classes':
            return <ManagementComponent title="Class" {...commonProps} apiEndpoint="classes" existingItems={allData.classes?.map(c => <li key={c.id} className="p-2 bg-gray-100 rounded-md">{c.name}</li>)} formFields={[{ name: 'name', label: 'Class Name', type: 'text', placeholder: "e.g., Third Year" }]} />
        case 'divisions':
            return <ManagementComponent title="Division" {...commonProps} apiEndpoint="divisions" existingItems={allData.divisions?.map(d => <li key={d.id} className="p-2 bg-gray-100 rounded-md">{d.name}</li>)} formFields={[{ name: 'name', label: 'Division Name', type: 'text', placeholder: "e.g., C" }]} />
        default:
            return null;
    }
};

const AdminDashboard = ({ allData, onAddData, isLoading, apiError }) => {
    const { useState, createElement } = React;
    const { useApi } = window.Hooks; // Access hook from global
    const { motion, AnimatePresence } = window.Animation;

    const [activeTab, setActiveTab] = useState('generate');
    const [timetable, setTimetable] = useState([]);
    const [selectedClass, setSelectedClass] = useState('');
    const [selectedDivision, setSelectedDivision] = useState('');
    const { isLoading: isGenerating, error: generationError, callApi: generateApi } = useApi();
    
    const handleGenerate = async () => {
        if (!selectedClass || !selectedDivision) return alert("Please select a class and division first.");
        setTimetable([]);
        try {
            const data = await generateApi('generate', 'POST', { class_id: selectedClass, division_id: selectedDivision });
            setTimetable(data.timetable);
        } catch (err) {}
    };

    const TabButton = ({ tabName, children }) => (
        <button onClick={() => setActiveTab(tabName)} className={`px-4 py-2 font-semibold rounded-md transition-colors ${activeTab === tabName ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}>
            {children}
        </button>
    );

    return createElement('div', null,
        createElement('div', { className: "flex space-x-2 justify-center bg-white p-2 rounded-lg shadow-sm" },
            createElement(TabButton, { tabName: "generate" }, "Generator"),
            createElement(TabButton, { tabName: "teachers" }, "Manage Teachers"),
            createElement(TabButton, { tabName: "courses" }, "Manage Courses"),
            createElement(TabButton, { tabName: "rooms" }, "Manage Rooms"),
            createElement(TabButton, { tabName: "classes" }, "Manage Classes"),
            createElement(TabButton, { tabName: "divisions" }, "Manage Divisions")
        ),
        createElement(AnimatePresence, { mode: "wait" },
            createElement(motion.div, { key: activeTab, initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -10 } },
                activeTab === 'generate' && createElement('div', { className: "text-center mt-6" },
                    createElement('div', { className: "flex justify-center items-center space-x-4 bg-white p-4 rounded-lg shadow" },
                        createElement('select', { value: selectedClass, onChange: e => setSelectedClass(e.target.value), className: "p-2 border rounded-md" },
                            createElement('option', { value: "" }, "Select Class"),
                            allData.classes?.map(c => createElement('option', { key: c.id, value: c.id }, c.name))
                        ),
                        createElement('select', { value: selectedDivision, onChange: e => setSelectedDivision(e.target.value), className: "p-2 border rounded-md" },
                            createElement('option', { value: "" }, "Select Division"),
                            allData.divisions?.map(d => createElement('option', { key: d.id, value: d.id }, d.name))
                        ),
                        createElement(motion.button, { onClick: handleGenerate, disabled: isGenerating, className: "bg-indigo-600 text-white font-bold py-2 px-6 rounded-lg shadow-lg hover:bg-indigo-700 disabled:bg-gray-400 transition-all transform hover:scale-105" },
                            isGenerating ? 'Generating...' : 'Generate Timetable'
                        )
                    ),
                    isGenerating && createElement('p', { className: "text-indigo-600 mt-4" }, "Generating schedule... please wait."),
                    generationError && createElement('div', { className: "mt-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg text-center" }, createElement('strong', null, "Error: "), generationError),
                    timetable.length > 0 && createElement(window.Components.TimetableGrid, { timetable, allData })
                ),
                createElement(ManagementTab, { allData, activeTab, onAddData, isLoading, apiError })
            )
        )
    );
};

// --- FIX: Expose the AdminDashboard component to the global window object ---
window.AdminDashboard = AdminDashboard;

