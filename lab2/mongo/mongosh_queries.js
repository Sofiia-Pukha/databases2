// запуск: mongosh university mongo/mongosh_queries.js
const col = db.student_profiles;

print("\n--- 1. Кількість документів і один профіль (find + проекція) ---");
print(col.countDocuments());
printjson(col.findOne({ _id: 42 }, { first_name: 1, last_name: 1, group: 1, stats: 1 }));

print("\n--- 2. Фільтр за вкладеним полем + сортування + ліміт ---");
printjson(col.find({ "group.faculty.id": 1, "stats.avg_grade": { $gte: 85 } },
                   { last_name: 1, "group.name": 1, "stats.avg_grade": 1 })
             .sort({ "stats.avg_grade": -1 }).limit(5).toArray());

print("\n--- 3. Пошук у масиві: студенти з оцінкою 100 з дисципліни id=2 ---");
print(col.countDocuments({ grades: { $elemMatch: { subject_id: 2, grade: 100 } } }));

print("\n--- 4. INSERT нового студента ---");
col.deleteOne({ _id: 999999 });
col.insertOne({
  _id: 999999, first_name: "Демо", last_name: "Монго", email: "demo@univ.ua",
  birth_date: new Date("2005-04-01"),
  group: { id: 1, name: "G-00001", course_year: 2,
           specialty: { id: 2, name: "Інженерія ПЗ" },
           faculty: { id: 1, name: "Факультет інформаційних технологій" } },
  grades: [], stats: { avg_grade: 0, grades_count: 0 }, achievements: []
});
printjson(col.findOne({ _id: 999999 }, { first_name: 1, last_name: 1 }));

print("\n--- 5. UPDATE: $push оцінки, $set, $inc ---");
col.updateOne({ _id: 999999 }, {
  $push: { grades: { subject_id: 2, subject: "Бази даних 1", credits: 5, semester_id: 8,
                     semester: "2025/2026 весна", grade: 95, date: new Date() } },
  $set:  { "stats.avg_grade": 95 },
  $inc:  { "stats.grades_count": 1 }
});
printjson(col.findOne({ _id: 999999 }, { grades: 1, stats: 1 }));

print("\n--- 6. Агрегація: середній бал по факультетах ---");
printjson(col.aggregate([
  { $group: { _id: "$group.faculty.name", students: { $sum: 1 },
              avg: { $avg: "$stats.avg_grade" } } },
  { $sort: { avg: -1 } }
]).toArray());

print("\n--- 7. Агрегація з $unwind: топ-3 дисципліни за середнім балом ---");
printjson(col.aggregate([
  { $unwind: "$grades" },
  { $group: { _id: "$grades.subject", avg: { $avg: "$grades.grade" }, cnt: { $sum: 1 } } },
  { $sort: { avg: -1 } }, { $limit: 3 }
], { allowDiskUse: true }).toArray());

print("\n--- 8. Індекси колекції ---");
printjson(col.getIndexes().map(i => i.name));

print("\n--- 9. Explain пошуку переможців олімпіад ---");
const ex = col.find({ achievements: { $elemMatch: { type: "olympiad", level: "international", place: 1 } } })
              .explain("executionStats");
printjson({ nReturned: ex.executionStats.nReturned,
            keysExamined: ex.executionStats.totalKeysExamined,
            docsExamined: ex.executionStats.totalDocsExamined,
            timeMs: ex.executionStats.executionTimeMillis });

print("\n--- 10. DELETE ---");
printjson(col.deleteOne({ _id: 999999 }));
