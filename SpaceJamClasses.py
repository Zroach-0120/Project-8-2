from panda3d.core import NodePath, Vec3, CollisionNode, CollisionSphere, CollisionHandlerQueue, CollisionRay, Filename
import random, math
from direct.task import Task
from CollideObjectBase import *
from direct.task.Task import TaskManager
import DefensePaths as defensePaths
from direct.interval.IntervalGlobal import Sequence

class Universe(InverseSphereCollideObject):
    def __init__(self, loader, modelPath, parentNode, nodeName, texPath, posVec, scaleVec):
        
        super().__init__(loader, modelPath, parentNode, nodeName, Vec3(0,0,0), 2)
        
        self.modelNode.reparentTo(parentNode)
        self.modelNode.setPos(posVec)
        self.modelNode.setScale(scaleVec)
        self.modelNode.setName(nodeName)
        
        tex = loader.loadTexture(texPath)
        self.modelNode.setTexture(tex, 1)


class Planet(SphereCollideObject):
    def __init__(self, loader, modelPath, parentNode, nodeName, texPath, posVec, scaleVec):
        super().__init__(loader, modelPath, parentNode, nodeName, Vec3(0, 0, 0), 1.5)
        
        self.modelNode.setPos(posVec)
        self.modelNode.setScale(scaleVec)
        
        tex = loader.loadTexture(texPath)
        self.modelNode.setTexture(tex, 1)
        
        self.collisionNode.node().addSolid(CollisionSphere(0, 0, 0, 5))
        self.collisionNode.show()


from panda3d.core import CollisionNode, CollisionSphere, Vec3

from direct.particles.ParticleEffect import ParticleEffect
from panda3d.core import NodePath, Vec3, CollisionNode, CollisionSphere

class Drone(CollideableObject):
    droneCount = 0
    droneInstances = []
    dronePool = []

    def __init__(self, loader, modelPath, parentNode, nodeName, texPath, posVec, scaleVec):
        super().__init__(loader, modelPath, parentNode, nodeName)

        self.modelNode.reparentTo(parentNode)
        self.modelNode.setPos(posVec)

        # Force scaleVec to be Vec3 type
        if not isinstance(scaleVec, Vec3):
            scaleVec = Vec3(scaleVec, scaleVec, scaleVec)
        self.modelNode.setScale(scaleVec)

        self.modelNode.setName(nodeName)

        tex = loader.loadTexture(texPath)
        self.modelNode.setTexture(tex, 1)

        # === COLLISION SETUP ===
        radius = scaleVec.getX() *1.2  
        collSphere = CollisionSphere(0, 0, 0, radius)

        collNode = CollisionNode(nodeName + "_cnode")
        collNode.addSolid(collSphere)

       
        self.collisionNodePath = self.modelNode.attachNewNode(collNode)
        self.collisionNodePath.show()  # Remove after debugging

        
        self.explodeNode = NodePath(f"{nodeName}_explodeNode")
        self.explodeNode.reparentTo(parentNode)  

        self.explodeEffect = ParticleEffect()
        self.explodeEffect.loadConfig("Assets/Part-Efx/basic_xpld_efx.ptf") 

        
        Drone.droneCount += 1
        Drone.droneInstances.append(self)

    def explode(self):
        print(f"Drone {self.modelNode.getName()} exploding!")

        # Position explosion node at drone's current position relative to parent
        self.explodeNode.setPos(self.modelNode.getPos(self.modelNode.getParent()))
        self.explodeEffect.start(self.explodeNode)

        if self in Drone.droneInstances:
            Drone.droneInstances.remove(self)

        self.modelNode.removeNode()

    @staticmethod
    def return_to_pool(drone):
        """Returns the drone to the pool when it is destroyed."""
        if drone in Drone.droneInstances:
            Drone.droneInstances.remove(drone)
        Drone.dronePool.append(drone.modelNode)
        drone.modelNode.removeNode()


class SpaceStation(CapsuleCollideableObject):
    def __init__(self, loader, modelPath, parentNode, nodeName, texPath, posVec, scaleVec):
        super().__init__(loader, modelPath, parentNode, nodeName, 1, -1, 5, 1, -1, -5, 1.5)
        
        self.modelNode.setPos(posVec)
        self.modelNode.setScale(scaleVec)
        self.modelNode.setName(nodeName)

        tex = loader.loadTexture(texPath)
        self.modelNode.setTexture(tex, 1)
    

class Missile(SphereCollideObject):
     fireModels = {}
     cNodes = {}
     collisionSolids = {}
     Intervals = {}
     missileCount = 0

     def __init__(self, loader: Loader, modelPath: str, parentNode: NodePath, nodeName: str, posVec: Vec3, scaleVec: float = 1.0):
         super(Missile, self).__init__(loader, modelPath, parentNode, nodeName, Vec3(0,0,0), 3.0)
         self.modelNode.setScale(scaleVec)
         self.modelNode.setPos(posVec)
         Missile.missileCount += 1
         Missile.fireModels[nodeName] = self.modelNode
         Missile.cNodes[nodeName] = self.collisionNode
         Missile.collisionSolids[nodeName] = self.collisionNode.node().getSolid(0)
         Missile.cNodes[nodeName].show()
         print("Fire rocket #" + str(Missile.missileCount))

class Wanderer(SphereCollideObject):
    numWanderers = 0

    def __init__(self, loader: Loader, modelPath: str, parentNode: NodePath, modelName: str,
                 scaleVec: float, texPath: str, startPos: Vec3):
        super(Wanderer, self).__init__(loader, modelPath, parentNode, modelName, Vec3(0, 0, 0), 3.2)

        self.modelNode.setScale(scaleVec)
        tex = loader.loadTexture(texPath)
        self.modelNode.setTexture(tex, 1)

        Wanderer.numWanderers += 1
        uniqueName = f"Traveler-{Wanderer.numWanderers}"

        # Offset the animation path by startPos
        posInterval0 = self.modelNode.posInterval(20, startPos + Vec3(300, 6000, 500), startPos=startPos)
        posInterval1 = self.modelNode.posInterval(20, startPos + Vec3(700, -2000, 100), startPos=startPos + Vec3(300, 6000, 500))
        posInterval2 = self.modelNode.posInterval(20, startPos + Vec3(0, -900, -1400), startPos=startPos + Vec3(700, -2000, 100))

        self.travelRoute = Sequence(posInterval0, posInterval1, posInterval2, name=uniqueName)
        self.travelRoute.loop()


class Orbiter(CapsuleCollideableObject):
    
    numOrbits = 0
    velocity = 0.005
    cloudTimer = 240

    def __init__(self, loader: Loader, taskMgr: TaskManager, modelPath: str, parentNode: NodePath, nodeName: str, 
                 scaleVec: Vec3, texPath: str, centralObject: PlacedObject, orbitRadius: float, 
                 orbitType: str, staringAt: Vec3):
        
        super().__init__(loader, modelPath, parentNode, nodeName, 1, -1, 5, 1, -1, -5, 1.5)

        
        self.taskMgr = taskMgr
        self.orbitType = orbitType

        self.modelNode.setScale(0.00005)
        tex = loader.loadTexture(texPath)
        self.modelNode.setTexture(tex, 1)
        
        self.orbitObject = centralObject
        self.orbitRadius = orbitRadius
        self.staringAt = staringAt

        
        Orbiter.numOrbits += 1
        self.numOrbits = Orbiter.numOrbits

        self.cloudClock = 0
        self.taskFlag = "Traveler-" + str(self.numOrbits)
        
        # Add the orbit task.
        self.taskMgr.add(self.Orbit, self.taskFlag)

    def Orbit(self, task):
        if self.orbitType == "MLB":
            positionVec = defensePaths.BaseballSeams(task.time * Orbiter.velocity, self.numOrbits, 2.0, 1.0)
            newPos = positionVec * self.orbitRadius + self.orbitObject.modelNode.getPos()
            self.modelNode.setPos(newPos)
        elif self.orbitType == "Cloud":
            if self.cloudClock < Orbiter.cloudTimer:
                self.cloudClock += 1
            else:
                self.cloudClock = 0
                positionVec = defensePaths.Cloud()
                newPos = positionVec * self.orbitRadius + self.orbitObject.modelNode.getPos()
                self.modelNode.setPos(newPos)
        
        self.modelNode.lookAt(self.staringAt.modelNode)
        return task.cont
      