import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from scipy.spatial import ConvexHull



if __name__=="__main__":
    turbineX = np.array([3.614835604537355493e+02,
            6.902024923547729713e+02,
            3.614835604537355493e+02,
            1.105631300734174829e+03,
            1.520891346672986856e+03,
            1.811266020039728801e+03,
            9.248753789537173589e+02,
            3.614835604537355493e+02,
            3.127808375536319545e+03,
            3.614835604537355493e+02,
            3.614835604537355493e+02,
            1.762806472721627188e+03,
            3.614835604537355493e+02,
            2.226544921431172952e+03,
            2.987808375536319545e+03,
            3.614835604537355493e+02,
            3.127808375536319545e+03,
            1.655421354669498214e+03,
            1.357865247386577721e+03,
            3.120481934359736897e+03,
            3.104942936555477445e+03,
            3.614835604537355493e+02,
            3.112551679052246527e+03,
            2.354370268946103806e+03,
            1.632316192043911997e+03,
            1.147432220873545020e+03,
            3.674516816054892843e+02,
            3.614835604537355493e+02,
            1.957071737933395980e+03,
            1.400554135301623774e+03,
            2.230961866529078179e+03,
            2.515228261756529719e+03,
            1.829760320849775098e+03,
            3.127808375536319545e+03,
            2.727070203644807407e+03,
            5.014835604537355493e+02,
            2.178303344037629358e+03,
            1.029766018973874679e+03,
            3.127808375536319545e+03,
            1.672481844959393584e+03,
            2.159738833792613605e+03,
            2.185248140602725471e+03,
            3.645293543717713760e+02,
            2.509986834631400143e+03,
            3.127808375536319545e+03,
            2.591674154538948642e+03,
            3.614835604537355493e+02,
            3.093683916953349581e+03,
            2.144545653907336145e+03,
            7.791598552459911389e+02,
            2.655920899256162102e+03,
            1.426381904732668772e+03,
            3.127808375536319545e+03,
            1.350856527857553601e+03,
            7.061835508664232748e+02,
            7.689368758632505205e+02,
            3.127808375536319545e+03,
            1.965862429513586903e+03,
            2.421592093370628390e+03,
            3.127808375536319545e+03,
            2.789749548242467426e+03,
            2.537897722665615220e+03,
            1.397662977549329071e+03,
            3.614835604537355493e+02,
            2.750904652822207936e+03,
            2.580919099907046984e+03,
            2.378586332265686451e+03,
            2.591522777404694352e+03,
            1.084780624570683358e+03,
            9.735392471243835644e+02,
            3.614835604537355493e+02,
            1.876356464235151179e+03,
            3.029772302729407784e+03,
            1.152010943319611215e+03,
            2.136216473109634080e+03,
            3.614835604537355493e+02,
            1.274452560471475863e+03,
            3.119041667854878142e+03,
            1.595636897450771812e+03,
            1.520243656737332458e+03,
            1.497100901383933888e+03])

    turbineY = np.array([1.599526665011821706e+03,
            3.141621927630518258e+03,
            6.251542828190332557e+02,
            2.787608545661323660e+03,
            2.494074631258146837e+03,
            2.063871844932951262e+03,
            3.131384048465556589e+03,
            1.134183627110620591e+03,
            1.673865972226926715e+03,
            2.996225543545248001e+03,
            2.036313123705431963e+03,
            1.086682427215454254e+03,
            1.274183627110620819e+03,
            3.141621927630518258e+03,
            3.928969349018635739e+02,
            2.245087575607602048e+03,
            1.008542401980916566e+03,
            3.141621927630518258e+03,
            3.141537994720657025e+03,
            2.157550464947473756e+03,
            2.837273186756600353e+03,
            1.806183701651517595e+03,
            7.798379545694870103e+02,
            4.234841545256115865e+02,
            3.928969349018635739e+02,
            3.141621927630518258e+03,
            9.232487557373904110e+02,
            2.596676401475739567e+03,
            1.926867159897431748e+03,
            1.350745313221746528e+03,
            2.341853410170900588e+03,
            2.518655699893974997e+03,
            3.141621927630518258e+03,
            3.928969349018635739e+02,
            2.672897327351328840e+03,
            3.928969349018635739e+02,
            1.817409420645914679e+03,
            2.415722188973576976e+03,
            2.413380194872168886e+03,
            2.826871826548681838e+03,
            6.716747616093671240e+02,
            2.698129648436210573e+03,
            2.757025505329294447e+03,
            2.059615432840173526e+03,
            1.358666380661142739e+03,
            3.928969349018635739e+02,
            3.928969349018635739e+02,
            6.411151810127153112e+02,
            1.180929035880993069e+03,
            1.413816905332311535e+03,
            8.915272249134816320e+02,
            3.928969349018635739e+02,
            3.141621927630518258e+03,
            8.420540061546596462e+02,
            4.165415894632068330e+02,
            2.002114142972533045e+03,
            1.946302633834633298e+03,
            9.105959849214110591e+02,
            1.658307941189550093e+03,
            1.148542401980916566e+03,
            1.860995187093475352e+03,
            1.055894892497860610e+03,
            1.542930825304709288e+03,
            1.421201031373161186e+03,
            3.141621927630518258e+03,
            1.412304042695014232e+03,
            3.137955330206404142e+03,
            2.897402748791984777e+03,
            4.431476578190211058e+02,
            8.471718863267547022e+02,
            3.141621927630518258e+03,
            3.928969349018635739e+02,
            2.520860465363695312e+03,
            1.615024056935843873e+03,
            3.928969349018635739e+02,
            7.651542828190332557e+02,
            3.928969349018635739e+02,
            2.982694461161742765e+03,
            1.236982756675157589e+03,
            2.220683215448743795e+03,
            2.041081933032466850e+03])

    nRows = 9
    rotor_diameter = 70.
    nTurbs = nRows**2

    """set up 3D aspects of wind farm"""
    H1_H2 = np.array([])
    for i in range(nTurbs/2):
        H1_H2 = np.append(H1_H2, 0)
        H1_H2 = np.append(H1_H2, 1)
    if len(H1_H2) < nTurbs:
        H1_H2 = np.append(H1_H2, 0)

    fig = plt.gcf()
    ax = fig.gca()

    spacingGrid = 5.
    points = np.linspace(start=spacingGrid*rotor_diameter, stop=nRows*spacingGrid*rotor_diameter, num=nRows)
    xpoints, ypoints = np.meshgrid(points, points)
    turbineXstart = np.ndarray.flatten(xpoints)
    turbineYstart = np.ndarray.flatten(ypoints)
    points = np.zeros((nTurbs,2))
    for j in range(nTurbs):
        points[j] = (turbineXstart[j],turbineYstart[j])
    hull = ConvexHull(points)

    ax.set_aspect('equal')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.get_xaxis().tick_bottom()
    ax.get_yaxis().tick_left()
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)


    for simplex in hull.simplices:
        ax.plot(points[simplex, 0], points[simplex, 1], 'k--')

    for j in range(nTurbs):
        if H1_H2[j] == 0:
            ax.add_artist(Circle(xy=(turbineX[j],turbineY[j]),
                      radius=rotor_diameter/2., fill=False, edgecolor='blue'))
        else:
            ax.add_artist(Circle(xy=(turbineX[j],turbineY[j]),
                      radius=rotor_diameter/2., fill=False, edgecolor='red'))

    # ax.axis([min(turbineXopt)-200,max(turbineXopt)+200,min(turbineYopt)-200,max(turbineYopt)+200])
    # plt.axes().set_aspect('equal')
    # plt.legend()

    # plt.title('Optimized Turbine Layout')
    # plt.savefig('optimizedLayout.pdf', transparent=True)
    plt.axis('off')
    # plt.title('Optimized Turbine Layout\nShear Exponent = 0.1\nFarm Size = 144 rotor diameters squared')
    plt.show()
